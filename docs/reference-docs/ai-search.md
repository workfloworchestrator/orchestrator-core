# AI / Hybrid Search

This document describes the **AI search subsystem**: a schema-agnostic hybrid search engine that finds subscriptions, products, processes, and workflows by combining semantic (vector), fuzzy (trigram), and structured (hierarchical) matching over a single PostgreSQL index.

It is distinct from the classic [Search](search.md) implementations (`subscriptions_search` full-text view and DB-table filtering). Where those match keywords, the AI search subsystem understands *fields*: every attribute of every entity is indexed as its own row, addressable by a hierarchical path, and searchable by meaning, spelling, or exact value.

> **Background.** The design and rationale are described in depth in [PostgreSQL hybrid search](https://timfrohlich.com/blog/postgresql-hybrid-search). This page documents the concrete implementation in `orchestrator/core/search/`.

<!-- TOC -->
- [AI / Hybrid Search](#ai-hybrid-search)
  - [Overview](#overview)
  - [Data model](#data-model)
    - [`ai_search_index`](#ai_search_index)
    - [Indexes](#indexes)
    - [Field types and extensions](#field-types-and-extensions)
    - [Supporting tables](#supporting-tables)
  - [Indexing pipeline](#indexing-pipeline)
    - [Traversal: models to paths](#traversal-models-to-paths)
    - [The Indexer](#the-indexer)
    - [What triggers indexing](#what-triggers-indexing)
  - [Embeddings](#embeddings)
  - [Retrieval and ranking](#retrieval-and-ranking)
    - [Retriever selection](#retriever-selection)
    - [Hybrid ranking (Reciprocal Rank Fusion)](#hybrid-ranking-reciprocal-rank-fusion)
    - [Fuzzy, semantic, and structured retrievers](#fuzzy-semantic-and-structured-retrievers)
    - [The query builder and EAV pivot](#the-query-builder-and-eav-pivot)
    - [Filters](#filters)
    - [Pagination](#pagination)
  - [Query language and persistence](#query-language-and-persistence)
  - [API, GraphQL, and MCP surfaces](#api-graphql-and-mcp-surfaces)
    - [Search fallback waterfall](#search-fallback-waterfall)
  - [Settings](#settings)
  - [Operational notes](#operational-notes)
<!-- TOC -->

## Overview

The subsystem combines **four search modalities** over one index:

| Modality | Backed by | Postgres feature | Operator |
|----------|-----------|------------------|----------|
| **Semantic** | vector embeddings | `pgvector` (HNSW, L2) | `<->` |
| **Fuzzy** | trigrams | `pg_trgm` word similarity | `<%`, `word_similarity()` |
| **Structured** | hierarchical paths | `ltree` | `~`, `@>`, `<@` |
| **Exact / typed** | typed value column | casts + comparisons | `=`, `ilike`, `~*`, numeric/date casts |

A search request is turned into a **query plan** (a typed `Query` object), which the engine routes to a **retriever**. When both a text term and an embedding are available the retriever fuses semantic and fuzzy results with Reciprocal Rank Fusion; otherwise it uses whichever single modality applies. Results are entities (not fields), ranked and keyset-paginated.

The whole subsystem is part of the **core** runtime (its dependencies `litellm`, `pgvector`, and `sqlalchemy-utils` are core, not optional). Only the MCP *server mount* is gated by the `mcp` extra. Embeddings are optional at runtime: with `EMBEDDING_API_ENABLED=False`, indexing stores rows with `embedding = NULL` and search silently degrades to fuzzy/structured — nothing errors.

```
                indexing (write path)                         search (read path)
  domain models ──► traverse ──► Indexer ──► ai_search_index ──► retriever ──► ranked entities
  (Subscription,    (ltree      (hash diff,   (EAV: 1 row per     (fuzzy /       (RRF fused,
   Product,          paths +     embed batch,   entity × field      semantic /     keyset
   Process,          typed       upsert)        path)               hybrid /       paginated)
   Workflow)         values)                                        structured)
```

## Data model

### `ai_search_index`

The heart of the subsystem is one **entity–attribute–value (EAV)** table (`orchestrator/core/db/models.py`, migration `2026-04-13_262744958e0c_add_ai_search_tables.py`). Each scalar field of each entity is stored as its own row:

| column | type | purpose |
|--------|------|---------|
| `entity_type` | `TEXT NOT NULL` | `SUBSCRIPTION` / `PRODUCT` / `PROCESS` / `WORKFLOW` |
| `entity_id` | `UUID NOT NULL` | the entity this field belongs to |
| `entity_title` | `TEXT` | human-readable label for the entity |
| `path` | `LTREE NOT NULL` | hierarchical field path, e.g. `subscription.node.name` |
| `value` | `TEXT NOT NULL` | the field value, stringified |
| `value_type` | `field_type NOT NULL` | how to interpret/compare `value` |
| `embedding` | `VECTOR(EMBEDDING_DIMENSION)` | embedding of the value text; `NULL` when not embeddable |
| `content_hash` | `VARCHAR(64) NOT NULL` | SHA-256 of the field, for change detection |

The primary key is composite: `(entity_id, path)`. One entity therefore contributes many rows — one per leaf field — which is why the table can hold millions of rows while the set of distinct *paths* stays schema-sized (see [Structured Search Field Paths](search.md#structured-search-field-paths) for the derived `ai_search_paths` table that exploits this).

### Indexes

Each index is paired with the modality it serves:

| index | definition | serves |
|-------|------------|--------|
| `ix_flat_embed_hnsw` | `HNSW (embedding vector_l2_ops) WITH (m=16, ef_construction=64)` | semantic NN via L2 distance (`<->`) |
| `ix_flat_value_trgm` | `GIN (value gin_trgm_ops)` | fuzzy word-similarity (`<%`, `word_similarity`) |
| `ix_flat_path_gist` | `GIST (path gist_ltree_ops)` | ltree matching (`~`, `@>`, `<@`) |
| `ix_flat_path_btree` | `btree (path)` | exact path equality (the EAV pivot) |
| `ix_ai_search_index_entity_id` | `btree (entity_id)` | candidate lookups by entity |
| `idx_ai_search_index_content_hash` | `btree (content_hash)` | change detection during indexing |

Note the operator-class coupling: HNSW is built with **`vector_l2_ops`**, so semantic and hybrid retrieval use **L2 distance (`<->`)**, not cosine (`<=>`).

### Field types and extensions

`value_type` is the Postgres enum `field_type`, generated at migration time from `FieldType` (`orchestrator/core/search/core/types.py`):

`string`, `integer`, `float`, `boolean`, `datetime`, `uuid`, `block`, `resource_type`

The migration creates these extensions (guarded by `LLM_FORCE_EXTENSION_MIGRATION` or the absence of `vector`): `uuid-ossp`, `ltree`, `unaccent`, `pg_trgm`, `vector`.

### Supporting tables

- **`ai_search_paths`** — a derived distinct-paths table maintained by a refcount trigger, used to make `GET /api/search/paths` fast. Documented in [Structured Search Field Paths](search.md#structured-search-field-paths).
- **`search_queries`** — persists every executed query (`parameters` JSONB, `query_embedding`, `query_number`). `run_id` is a nullable FK to `agent_runs`: `NULL` for standalone API/MCP searches; set when a query belongs to an agent run. Enables re-running and exporting a query by `query_id`.
- **`agent_runs`** and **`graph_snapshots`** — state persistence (pydantic-graph snapshots, keyed `(run_id, sequence_number)`) for a *resumable external agent*. Core does not contain an LLM agent (see [Query language and persistence](#query-language-and-persistence)); these tables exist so an external agent can store and resume conversation state.

## Indexing pipeline

Located in `orchestrator/core/search/indexing/`.

### Traversal: models to paths

`BaseTraverser` (`traverse.py`) recursively walks a Pydantic domain model and emits `ExtractedField(path, value, value_type)` tuples:

- **Nested models** extend the ltree path and recurse.
- **Lists** append a numeric segment per element: `block.0`, `block.1`, …
- **Scalars** emit a leaf field. `value_type` is derived from the **type hint** (`FieldType.from_type_hint`), which unwraps `Annotated`/`Optional`/`Union`/`list`/`Literal`, maps `int/float/bool/str/datetime/UUID`, and maps `ProductBlockModel → block`, `IntEnum → integer`, other `Enum → string`.

The `LTREE_SEPARATOR` is `.`. Concrete traversers specialise how the root model is loaded:

| Traverser | Entity | Notes |
|-----------|--------|-------|
| `SubscriptionTraverser` | subscription | loads the specialized `SubscriptionModel` for the product |
| `ProductTraverser` | product | builds a *template* subscription for the product and extracts the block schema (block → `block`, each field → `resource_type`); product names are sanitized into valid ltree labels |
| `ProcessTraverser` | process | top-level fields only; excludes `traceback`, `failed_reason` |
| `WorkflowTraverser` | workflow | top-level fields only |

The `EntityConfig` for each entity type (table, traverser, PK column, root label, title paths) lives in `ENTITY_CONFIG_REGISTRY` (`registry.py`).

### The Indexer

`Indexer.run()` (`indexer.py`) streams entities and processes them in chunks (default 1000):

1. **Change detection** — one query prefetches existing `content_hash`es for the chunk. `content_hash = sha256(f"{path}:{value}:{value_type}:{entity_title}")`. Only new or changed fields are upserted; unchanged fields are skipped. (Because the hash includes `entity_title`, a title change re-indexes all of that entity's rows.) `--force-index` ignores existing hashes.
2. **Stale-path deletes** — paths that exist in the index but are no longer produced by traversal (`existing − current`) are deleted, batched to avoid stack-depth limits.
3. **Embedding batches** — embeddable string fields are accumulated against a token budget (`max_ctx − max_ctx * EMBEDDING_SAFE_MARGIN_PERCENT`) and flushed when the next item would exceed it, or when `EMBEDDING_MAX_BATCH_SIZE` is reached. Fields larger than the model context window are skipped. The embedded text is `f"{path}: {value}"`.
4. **Upsert** — `INSERT ... ON CONFLICT (entity_id, path) DO UPDATE SET entity_title, value, value_type, content_hash, embedding`.

`--dry-run` performs no writes. Only string-typed, non-empty values that don't *look* like a UUID/number/bool/date are embedded (`FieldType.is_embeddable`); everything else is stored with `embedding = NULL`.

### What triggers indexing

`run_indexing_for_entity(entity_kind, entity_id=None, ...)` (`tasks.py`) is the single entry point. It is invoked from:

- **Workflow steps** — `refresh_subscription_search_index` and `refresh_process_search_index` (`orchestrator/core/workflows/steps.py`) run at the end of create/modify/terminate workflows. They swallow exceptions so a failed re-index never fails the workflow.
- **REST PATCH endpoints** — product and process updates re-index the affected entity.
- **CLI** — `python main.py index subscriptions|products|processes|workflows` (with `--force-index`, `--dry-run`, `--show-progress`), and `python main.py index rebuild-paths` to rebuild `ai_search_paths`.

## Embeddings

Embeddings are generated through **litellm** (`orchestrator/core/search/core/embedding.py`), imported lazily because the import itself is expensive; when `EMBEDDING_API_ENABLED` is set, the import is pre-warmed at app startup.

- **Indexing** uses `EmbeddingIndexer.get_embeddings_from_api_batch()` (synchronous, batched). It calls `litellm.embedding(model=EMBEDDING_MODEL, input=[lowercased texts], ...)` and **truncates each vector to `EMBEDDING_DIMENSION`**.
- **Live queries** use `QueryEmbedder.generate_for_text_async()` (async, `timeout=5s`, `max_retries=0` — prioritising latency). It returns `None` when the API is disabled or the text is empty; callers treat `None` as "fall back to fuzzy/structured".

All embedding errors degrade gracefully to empty/`None` rather than raising.

Because `EMBEDDING_DIMENSION` is baked into the `embedding` column type, changing it requires the **`embedding resize` CLI** (`python main.py embedding resize`), which deletes all indexed rows and `ALTER`s the vector columns to the new dimension (followed by a re-index).

## Retrieval and ranking

Located in `orchestrator/core/search/retrieval/` and `orchestrator/core/search/query/`.

### Retriever selection

`RetrieverType` is `fuzzy`, `semantic`, or `hybrid`. The engine derives two inputs from the query text (`SearchMixin`):

- `vector_query` — the text to embed (skipped when the text is a UUID).
- `fuzzy_term` — the trigram term, populated **only for single-word text**. Multi-word free text is semantic-only under auto-routing unless an explicit `retriever` override is given.

Routing (`Retriever._plan`):

| Available | Retriever |
|-----------|-----------|
| embedding **and** fuzzy term | `RrfHybridRetriever` |
| embedding only | `SemanticRetriever` |
| fuzzy term only | `FuzzyRetriever` |
| neither (filters only) | `StructuredRetriever` |

Process entities that would route to fuzzy/hybrid are promoted to `ProcessHybridRetriever`, which additionally fuzzy-searches the latest process step's `state` JSONB. If embedding generation fails, auto-routing degrades to fuzzy.

### Hybrid ranking (Reciprocal Rank Fusion)

`RrfHybridRetriever` (`retrieval/retrievers/hybrid.py`) fuses the two modalities with **Reciprocal Rank Fusion** plus a **perfect-match boost**. Per matched entity it computes:

- `avg_semantic_distance` = mean L2 distance of the entity's field embeddings to the query vector (NULL embeddings coalesced to `1.0`);
- `avg_fuzzy_score` = mean `word_similarity(term, value)` over matched fields;
- ranks by `dense_rank()`: `sem_rank` ascending on distance, `fuzzy_rank` descending on fuzzy score.

The fused score (`compute_rrf_hybrid_score_sql`) is:

```
rrf      = 1/(k + sem_rank) + 1/(k + fuzzy_rank)          # k = 60
rrf_max  = n_sources / (k + 1)                            # n_sources = 2
beta     = rrf_max + rrf_max * margin_factor              # margin_factor = 0.05
perfect  = 1 if avg_fuzzy_score >= 0.9 else 0
fused    = rrf + beta * perfect
score    = fused / (beta + rrf_max)                       # normalized to [0, 1]
```

Because `beta > rrf_max`, any **perfect match** (average fuzzy similarity ≥ 0.9) always outranks any non-perfect result — exact text hits float to the top above semantic-only neighbours. Results are ordered `score DESC, entity_id ASC`.

### Fuzzy, semantic, and structured retrievers

- **Fuzzy** (`fuzzy.py`) — filters `value_type IN (string, uuid, block, resource_type)` and `'<term>' <% value`; score = `max(word_similarity(term, value))` per entity.
- **Semantic** (`semantic.py`) — filters `embedding IS NOT NULL`; score = `1 / (1 + min(embedding <-> :query_vector))` per entity, so a smaller distance yields a higher, [0,1]-bounded score.
- **Structured** (`structured.py`) — no relevance ranking (`score = 1.0`); orders by an optional `order_by` field materialized from the EAV rows, and emits `highlight_matches` for the positive filter leaves.

### The query builder and EAV pivot

`query/builder.py` turns a query plan into SQL:

- `build_candidate_query` — `SELECT DISTINCT entity_id, entity_title FROM ai_search_index WHERE entity_type = :t` plus the filter tree compiled to correlated `EXISTS` subqueries.
- **EAV → columns pivot** — to return or aggregate specific fields, rows are pivoted with `MAX(CASE WHEN path = :p THEN value END) AS <alias>` grouped by `entity_id`. This powers inline `response_columns` and aggregations (`COUNT/SUM/AVG/MIN/MAX`, temporal `date_trunc` grouping, and cumulative window sums).
- `build_paths_query` — reads the derived `ai_search_paths` table for field-path autocomplete (see [Structured Search Field Paths](search.md#structured-search-field-paths)).

The engine (`query/engine.py`) orchestrates: generate an embedding only when needed, route to a retriever, apply it, and fetch `limit + 1` rows to compute `has_more`.

### Filters

Structured filtering is a typed, bounded tree (`filters/`):

- **`PathFilter`** — a predicate over one path: `{path, condition, value_kind}`. It adds a **type guard** (`value_type IN <types matching the value kind>`) so a numeric filter never matches a string row. A dotless "global" path (e.g. `status`) matches any path *ending* in that component; a dotted path matches exactly.
- **`FilterTree`** — a recursive AND/OR tree (max depth 5). Each leaf compiles to a correlated `EXISTS (SELECT 1 FROM ai_search_index WHERE entity_id = ... AND <predicate>)`; `not_has_component` compiles to `NOT EXISTS`.
- **Condition types** (union tried in order): `DateFilter` (timestamp casts, `between` half-open), `NumericFilter` (bigint/double casts, `between`), `StringFilter` (`ilike`, wildcard required), `ContainsFilter` (POSIX `~*`), `LtreeFilter` (`matches_lquery ~`, `is_ancestor @>`, `is_descendant <@`, `has_component`, `ends_with`), and `EqualityFilter` (`eq`/`neq`, case-insensitive, boolean-aware) last as the most generic.

Requests may also supply an Elasticsearch-style DSL, which is auto-converted to a `FilterTree` (`filters/elastic_dsl.py`).

### Pagination

All retrievers use **keyset (cursor) pagination** rather than `OFFSET`: ranked retrievers page on `(score, entity_id)`, structured on `(order_value, entity_id)` or `entity_id`. The cursor encodes the last row's sort key, so pages stay stable as data changes.

## Query language and persistence

A search is a typed `Query` (`query/queries.py`), a discriminated union:

| Query | Purpose | Limit |
|-------|---------|-------|
| `SelectQuery` | return matching entities | ≤ 100 |
| `ExportQuery` | bulk export matching entities | ≤ 10000 |
| `CountQuery` | count (optionally grouped) | — |
| `AggregateQuery` | aggregations over matched entities | — |

Mixins add behavior: `SearchMixin` (query text, retriever, response columns), `GroupingMixin` (group-by, temporal grouping, cumulative, order-by, with validation), and `AggregationMixin`.

`QueryState` (`query/state.py`) wraps a query with its embedding and persists it to `search_queries`; `load_from_id(query_id)` re-validates the stored JSONB back into the typed query (clamping legacy limits). Validation (`query/validation.py`) checks lquery syntax, path existence against the live index, filter/field-type compatibility, and aggregation/grouping constraints before any SQL runs.

**The LLM agent is not part of orchestrator-core.** Core exposes the *tools* an agent needs (over MCP/REST) and persists query and graph state, but the agent loop itself lives in an external package. A typical agent flow is: `discover_filter_paths` → `get_valid_operators` → `search`/`aggregate` (which persist a `query_id`) → `export_query`.

## API, GraphQL, and MCP surfaces

All three surfaces delegate to the same engine, query-state, and definitions code.

**REST** — mounted at `/api/search` (behind auth):

| Endpoint | Purpose |
|----------|---------|
| `POST /subscriptions`, `/workflows`, `/products`, `/processes` | run a `SelectQuery`; retriever auto-selected |
| `GET /paths` | field-path autocomplete (from `ai_search_paths`) |
| `GET /definitions` | operator/UI-type matrix per field type |
| `GET /queries/{id}` · `/results` · `/export` | re-run or export a saved query |

**GraphQL** — fields `search`, `search_paths`, `search_definitions`, `search_query_results`, `search_query`, `search_query_export` (`graphql/resolvers/search.py`), mirroring the REST surface.

**MCP / agent tools** — mounted at `/api/agent`, exposed as read-only MCP tools when `MCP_ENABLED` and the `mcp` extra are present: `search`, `aggregate`, `discover_filter_paths`, `get_valid_operators`, `resolve_entity`, `export_query` (plus non-search workflow/process helpers).

### Search fallback waterfall

The MCP `search` tool runs `execute_search_with_fallback` (`search/fallback.py`): it first tries the exact structured query, then — if the result is empty and free text is present — **broadens** in up to `effort` passes (`LOW=0`, `MEDIUM=1`, `HIGH=3`):

1. drop loose `like`/string filters but keep high-signal `eq`/range/component filters;
2. drop all filters, use `HYBRID`;
3. drop all filters, use `SEMANTIC`.

When `EMBEDDING_API_ENABLED` is off, `SEMANTIC`/`HYBRID` passes degrade to `FUZZY`. The response reports which `search_type` was used and whether a fallback fired.

## Settings

`LLMSettings` (`orchestrator/core/settings.py`, instance `llm_settings`):

| setting | default | purpose |
|---------|---------|---------|
| `EMBEDDING_API_ENABLED` | `False` | master switch; when off, search is fuzzy/structured only |
| `EMBEDDING_MODEL` | `openai/text-embedding-3-small` | litellm model id (`provider/model`) |
| `EMBEDDING_DIMENSION` | `1536` | vector size (100–2000); baked into column types |
| `EMBEDDING_API_KEY` / `EMBEDDING_API_BASE` | `""` / `None` | credentials / endpoint |
| `EMBEDDING_ENCODING_FORMAT` | `float` | litellm encoding format |
| `EMBEDDING_SAFE_MARGIN_PERCENT` | `0.1` | token-budget headroom per embedding batch |
| `EMBEDDING_FALLBACK_MAX_TOKENS` | `512` | context window when the model's is unknown |
| `EMBEDDING_MAX_BATCH_SIZE` | `None` | max items per embedding batch (`None` = unlimited) |
| `LLM_MAX_RETRIES` / `LLM_TIMEOUT` | `3` / `30` | litellm retry/timeout (indexing) |
| `LLM_FORCE_EXTENSION_MIGRATION` | `False` | force `CREATE EXTENSION` in the tables migration |

The only related `AppSettings` flag is `MCP_ENABLED` (`False`), which controls the `/mcp` mount. REST and GraphQL search routers are always registered.

## Operational notes

- **Embeddings off is a valid mode.** With `EMBEDDING_API_ENABLED=False`, indexing writes `embedding = NULL` and search runs fuzzy/structured. No configuration errors; semantic/hybrid simply become unavailable and auto-route to fuzzy.
- **Multi-word queries.** `fuzzy_term` is single-word only, so multi-word free text auto-routes to semantic. To force trigram matching on multi-word input, pass an explicit `retriever=hybrid`/`fuzzy`.
- **Resizing embeddings** requires the `embedding resize` CLI and a full re-index — the dimension is fixed in the column type.
- **Version note.** `ai_search_paths` and its trigger are added by migration `ca79fd834ba0` (2026-07-15); installations below that revision won't have it and `GET /api/search/paths` will fail until migrated.
- **Reference.** For the design narrative behind this implementation, see [PostgreSQL hybrid search](https://timfrohlich.com/blog/postgresql-hybrid-search).
