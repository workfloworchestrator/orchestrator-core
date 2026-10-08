# AI / Hybrid Search

AI / Hybrid Search finds subscriptions, products, processes and workflows by combining several
kinds of matching (by meaning, by spelling, by structure and by exact value) over a single
PostgreSQL index.

It exists because keyword search answers only one kind of question. A user who types
`amsterdam node` wants results even if the description says "Amsterdam router"; a user who types
`nod` wants results despite the typo; and a UI that offers "status is active **and** start date
after 2025-01-01" needs typed, per-field filtering. Classic keyword search does none of these
well. AI / Hybrid Search indexes **every field of every entity as its own row**, so all four
kinds of matching run against the same data.

It is the successor to the [classic search](search.md) implementations and is the search behind
`/api/search`, the GraphQL `search` field, and the orchestrator's agent tools.

## How it compares to classic search

|                | Classic search                                                          | AI / Hybrid Search                                                  |
|----------------|-------------------------------------------------------------------------|---------------------------------------------------------------------|
| Data structure | `subscriptions_search` materialized view, plus `WHERE` clauses on entity tables | `ai_search_index` table, one row per entity field                    |
| Matches on     | whole-word keywords in one text blob per subscription                    | individual field values, by meaning, spelling, exact value or path  |
| Query shape    | a query string, e.g. `tag:L2VPN -status:active`                          | free text plus a typed filter tree                                   |
| Entities       | subscriptions (text search); others by DB-column filtering               | subscriptions, products, processes, workflows                        |
| Freshness      | view refreshed at most once every two minutes                            | index updated automatically on process exit, or on demand via the CLI |
| Status         | text search on subscriptions is **deprecated** since 5.0                 | current                                                              |

Classic search is still in place and still documented in [Search](search.md). New integrations
should use AI / Hybrid Search.

## Key ideas

### One row per field

A traditional search index stores one document per record. This subsystem stores one row per
**field**, in a table called `ai_search_index`. A subscription with 40 fields contributes 40 rows. This includes, besides the fields of the domain model of a subscription, all "depends-on" products fields.

Each row records where the value came from as a dotted path like `subscription.node.name`,
stored in a PostgreSQL [`ltree`](https://www.postgresql.org/docs/current/ltree.html) column.
`ltree` is a column type for hierarchical labels; it lets the database ask "is this path below
`subscription.node`?" using an index, rather than by string matching.

Two things follow from this layout:

- A query can address one field precisely ("status equals active") without the engine knowing
  anything about the product model. The subsystem is schema-agnostic: new product blocks become
  searchable simply by being indexed.
- The number of *rows* grows with your data, but the number of distinct *paths* only grows with
  your schema. A UI that needs "which fields can I filter on?" reads the much smaller
  [`ai_search_paths`](#the-distinct-paths-table) table instead.

### Three ways to match

| Match type          | Answers                                    | Built on                                                        |
|---------------------|--------------------------------------------|-----------------------------------------------------------------|
| **Semantic**        | "which values *mean* something similar?"    | vector embeddings, compared with [pgvector](https://github.com/pgvector/pgvector) |
| **Fuzzy**           | "which values are *spelled* similarly?"     | trigrams, via the `pg_trgm` extension                            |
| **Structured**      | "which entities have a field under this path?" | `ltree` path operators                                        |

**Trigrams** are three-character slices of a word: `node` becomes `nod`, `ode`. Two strings that
share many trigrams are similar, so `nod` still matches `node` and typos still find their target.
This is what makes fuzzy matching tolerant of spelling.

Fuzzy search matches query terms independently. For example, `ACME LIR` can match
`ACME prefix LIR`, or an entity with `ACME` and `LIR` in different fields. Every term must
match somewhere in the entity; see [Ranking formulas](#ranking-formulas) for the thresholds.

### What embeddings add

An **embedding** is a vector (list) of numbers that represents the meaning of a piece of text. Texts with
similar meanings get numerically close vectors, so "closeness" becomes a distance calculation the
database can index and sort by.

Embeddings are what let a search for `amsterdam router` return a subscription described as
"AMS core node". There is no shared keyword, only shared meaning. They are generated by an
external embedding API (through [LiteLLM](https://docs.litellm.ai/)) and stored alongside the
value in the same row.

Embeddings are **optional**. See [Running without embeddings](#running-without-embeddings).

## How it works

### Indexing (write path)

```mermaid
flowchart LR
    A["Domain models<br/>Subscription, Product,<br/>Process, Workflow"] --> B["Traverse<br/>model to field paths"]
    B --> C["Diff<br/>content hash per field"]
    C --> D["Embed<br/>batched, text fields only"]
    D --> E[("ai_search_index<br/>one row per entity field")]
    C -.->|unchanged| F["skipped"]
```

A traverser walks a domain model and emits one `(path, value, type)` triple per leaf field.
Nested models extend the path; list elements get a numeric segment (`block.0`, `block.1`). The
field's type comes from the model's *type hint*, not from the value, so a field declared `str`
is still compared as a string when its value happens to look like a number.

Each field is hashed. Only fields whose hash changed are written, and paths that traversal no
longer produces are deleted, so re-indexing an unchanged entity does almost no work. Text values
are embedded in batches sized against the embedding model's context window; everything else is
stored with no embedding.

Indexing is triggered from three places:

- **Process exit**: whenever a process reaches a normal exit through the workflow engine — completed, failed,
  aborted, suspended or timed out awaiting a callback (but not when execution fails before reaching
  that exit path, such as after losing database access) — the process record is re-indexed. Completed, aborted, suspended and
  callback-timeout exits also re-index the subscriptions referenced by their final state. A failed
  step replaces that state with an error record, so a failed exit re-indexes only the process.
  This runs after the terminal status has been committed, so the indexed process
  carries its real status. It applies to every workflow that reaches this exit hook, including
  `validate_workflow` and the bare `@workflow` decorator, so no step wiring is needed. Failures are
  logged and swallowed by default, so a failed re-index never breaks a process; set
  `SEARCH_INDEXING_STRICT` to raise instead.
- **REST endpoints**: product and process updates re-index the entity they changed.
- **The CLI**: see [Building and refreshing the index](#building-and-refreshing-the-index).

### Searching (read path)

```mermaid
flowchart TD
    Q["Search request<br/>free text and/or filters"] --> C["Candidate entities<br/>filters compiled to EXISTS subqueries"]
    Q --> P["Pick a retriever<br/>based on available signals"]
    C --> R["Rank the candidates"]
    P --> R
    R --> O["Ranked entities<br/>keyset paginated"]
```

A request becomes a typed query object. Filters narrow the candidate entities; the free-text part
decides *how* those candidates are ranked. The engine picks the retriever automatically unless the
request names one:

| Available signals                      | Retriever      | Ranking                                             |
|----------------------------------------|----------------|------------------------------------------------------|
| Text **and** an embedding               | **Hybrid**     | trigram and semantic rankings fused (see [RRF](#ranking-formulas)) |
| Text that is a UUID                     | **Fuzzy**      | highest trigram similarity wins                      |
| Filters only                            | **Structured** | no relevance ranking; ordered by a chosen field      |
| Explicit `retriever: semantic`          | **Semantic**   | closest embedding wins; never chosen automatically   |

Free text is fuzzy-matched term by term and, when an embedding is available, ranked
semantically using the whole query. In a domain where most searches are identifiers, names and
descriptions, the trigram signal is the strongest one, so it is always included; the semantic source keeps
plain-language queries working when no field contains the words. The only text that is not
embedded is a UUID, which has no meaning to embed and routes to fuzzy matching.

Callers can override the retriever explicitly with `retriever: fuzzy`, `semantic` or `hybrid`.
If an override needs an embedding and none can be produced, the request fails with a clear error
rather than silently returning different results; under automatic routing the same situation
falls back to fuzzy matching of the query terms.

Process searches use a variant of the hybrid retriever that also searches the `state`
JSONB of the process's most recent step. Process steps are deliberately left out of the index to
keep its size manageable, so that column is read and matched at query time instead: candidates
are found with a substring `ILIKE` using the whole query, then scored with
`word_similarity(query_text, state_text)`. This last-step lookup does not split the query into
terms and never contributes a semantic score. Matches are reported under the path
`process.last_step.state`.

Results are entities, not fields, and are paginated with a keyset (cursor) rather than `OFFSET`,
so pages stay stable while data changes underneath.

## What you can search, and where

Four entity types are indexed: **subscriptions**, **products**, **processes** and **workflows**.
All three interfaces run the same engine.

| Interface   | Where                       | What it offers                                                                             |
|-------------|-----------------------------|--------------------------------------------------------------------------------------------|
| **REST**    | `/api/search` (authenticated) | `POST /subscriptions`, `/products`, `/processes`, `/workflows` to search; `GET /paths` for field autocomplete; `GET /definitions` for the operators valid per UI type; `GET /queries/{id}`, `/results`, `/export` to re-run or export a saved query |
| **GraphQL** | root fields                 | `search`, `searchPaths`, `searchDefinitions`, `searchQuery`, `searchQueryResults`, `searchQueryExport`, mirroring REST |
| **Agent tools** | `/api/agent`            | `search`, `aggregate`, `discover_filter_paths`, `get_valid_operators`, `resolve_entity`, `export_query`, exposed as read-only [MCP](mcp.md) tools when `MCP_ENABLED` is set |

The REST and GraphQL search routers are always registered, and the agent tools are ordinary REST
endpoints that are always available. Only surfacing them over MCP is opt-in: that needs
`MCP_ENABLED=True` and the `mcp` extra installed. See [MCP Server](mcp.md).

Queries are stored in `search_queries` and addressed by `query_id`, so a caller can page through,
re-run or export a search without re-sending it. The agent `search` and `aggregate` tools always
store their query and return the id. REST and GraphQL store it when a result has a next page, and
put the id in the page cursor, which is also what keeps paging consistent while data changes.

!!! note "The LLM agent itself is not part of orchestrator-core"

    Core provides the tools an agent calls and stores query and conversation state for it. The
    agent loop lives in a separate package. A typical agent sequence is
    `discover_filter_paths` → `get_valid_operators` → `search`/`aggregate` → `export_query`.

## Running it

### Enabling embeddings

Search works out of the box without any embedding configuration. To enable semantic and hybrid
retrieval, point the orchestrator at an embedding provider:

```shell
EMBEDDING_API_ENABLED=True
EMBEDDING_API_KEY=sk-...                        # your provider's API key
EMBEDDING_MODEL=openai/text-embedding-3-small   # default; any LiteLLM model id
EMBEDDING_DIMENSION=1536                        # must match the model's output size
```

The [5.0 upgrade guide](../guides/upgrading/5.0.md) covers first-time setup end to end, including
the required PostgreSQL extensions. All settings are listed under
[Settings](#settings).

### Running without embeddings

`EMBEDDING_API_ENABLED` defaults to `False`. Indexing then stores every row with
`embedding = NULL` and searches use fuzzy and structured retrieval only, so anything that would
have been ranked semantically falls back to fuzzy. Runtime embedding failures behave the same
way, except when a request names `semantic` or `hybrid` explicitly: those return an error rather
than falling back. See [Searching](#searching-read-path).

### Building and refreshing the index

Workflows keep subscriptions and processes up to date on their own. Use the CLI for the initial
build, and after bulk changes:

```shell
python main.py index subscriptions
python main.py index products
python main.py index processes
python main.py index workflows
```

Each command accepts:

| Option                | Effect                                                     |
|-----------------------|------------------------------------------------------------|
| `--<entity>-id UUID`  | index a single entity, e.g. `--subscription-id`             |
| `--force-index`       | re-index every field, ignoring the content hashes           |
| `--dry-run`           | make no database writes and no embedding calls              |
| `--show-progress`     | show a progress bar                                        |

`python main.py index rebuild-paths` recomputes the
[distinct-paths table](#the-distinct-paths-table) from scratch.

`python main.py search` runs individual search strategies from a shell (`structured`, `semantic`,
`fuzzy`, `hierarchical`, `hybrid`, plus `generate-schema` and `nested-demo`), and
`python main.py speedtest quick` measures query performance. These are exploration aids; the
`semantic`, `fuzzy` and `hybrid` commands force the retriever of the same name.

### Running a local embedding server

For a self-hosted endpoint, only OpenAI-compatible APIs are supported. To run
[all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) locally with
[Hugging Face TEI](https://github.com/huggingface/text-embeddings-inference):

```shell
docker run --rm -p 8080:80 ghcr.io/huggingface/text-embeddings-inference:cpu-1.8 \
    --model-id sentence-transformers/all-MiniLM-L6-v2
```

Point the orchestrator at it and declare the model's vector size:

```shell
EMBEDDING_API_BASE=http://localhost:8080/v1
EMBEDDING_DIMENSION=384
EMBEDDING_MAX_BATCH_SIZE=32
```

`EMBEDDING_MAX_BATCH_SIZE` and `EMBEDDING_FALLBACK_MAX_TOKENS` exist for models like this one,
whose limits LiteLLM cannot look up. They are not needed with hosted OpenAI models.

Changing `EMBEDDING_DIMENSION` also requires a resize (see below).

### Changing the embedding dimension

`EMBEDDING_DIMENSION` is baked into the vector column type, so it cannot be changed by
configuration alone:

```shell
python main.py embedding resize
```

!!! warning

    `embedding resize` **deletes every row** from `ai_search_index` and `search_queries` before
    altering the column and rebuilding the HNSW indexes. Re-index afterwards.

## Implementation reference

Everything below describes how the current implementation works. It is useful for debugging,
performance work and maintenance, but it is not a stable interface.

### Data model

`ai_search_index` is an entity-attribute-value (EAV) table: each scalar field of each entity is
one row.

| Column          | Type                          | Purpose                                                       |
|-----------------|-------------------------------|---------------------------------------------------------------|
| `entity_type`   | `TEXT NOT NULL`               | `SUBSCRIPTION` / `PRODUCT` / `PROCESS` / `WORKFLOW`            |
| `entity_id`     | `UUID NOT NULL`               | the entity this field belongs to                              |
| `entity_title`  | `TEXT`                        | human-readable label for the entity                           |
| `path`          | `LTREE NOT NULL`              | field path, e.g. `subscription.node.name`                     |
| `value`         | `TEXT NOT NULL`               | the field value, stringified                                  |
| `value_type`    | `field_type NOT NULL`         | how to interpret and compare `value`                          |
| `embedding`     | `VECTOR(EMBEDDING_DIMENSION)` | embedding of the value text; `NULL` when not embeddable        |
| `content_hash`  | `VARCHAR(64) NOT NULL`        | SHA-256 of the field, for change detection                    |

The primary key is `(entity_id, path)`. `value_type` is a PostgreSQL enum generated from
`FieldType`: `string`, `integer`, `float`, `boolean`, `datetime`, `uuid`, `block`,
`resource_type`.

The content hash covers `path`, `value`, `value_type` **and** `entity_title`, so renaming an
entity re-indexes all of its rows.

Only non-empty text values that do not *look* like a UUID, number, boolean or date are embedded.
The embedded text is `"{path}: {value}"`, which gives the model the field name as context.

Supporting tables:

- **`search_queries`**: stored queries, with their parameters as JSONB and their embedding.
  `run_id` is `NULL` for ordinary API and agent-tool searches, and set when the query belongs to
  an agent run. This is what `query_id` re-run, paging and export read from.
- **`agent_runs`** and **`graph_snapshots`**: conversation and graph state for an external
  resumable agent. Core writes and reads them but contains no agent itself.

### Indexes

Each index serves one match type:

| Index                            | Definition                                                        | Serves                                     |
|----------------------------------|-------------------------------------------------------------------|--------------------------------------------|
| `ix_flat_embed_hnsw_<entity type>` | `HNSW (embedding vector_l2_ops) WITH (m=16, ef_construction=64)`, partial on one `entity_type` | nearest-neighbour search by L2 distance (`<->`) |
| `ix_flat_value_trgm`             | `GIN (value gin_trgm_ops)`                                        | trigram filtering (`<%`)                    |
| `ix_flat_path_gist`              | `GIST (path gist_ltree_ops)`                                      | `ltree` matching (`~`, `@>`, `<@`)          |
| `ix_flat_path_btree`             | `btree (path)`                                                    | exact path equality, used by the EAV pivot  |
| `ix_ai_search_index_entity_id`   | `btree (entity_id)`                                               | candidate lookups by entity                 |
| `idx_ai_search_index_content_hash` | `btree (content_hash)`                                          | change detection during indexing            |

The HNSW indexes use `vector_l2_ops`, so semantic ranking uses **L2 distance (`<->`)**, not cosine
distance.

There is one partial HNSW index per entity type rather than a single shared one. A search covers a
single entity type, and on a shared index that restriction is a post-filter: the scan walks the
nearest vectors of *all* types and can exhaust its candidate frontier before reaching a single row
of the type being searched. A partial index makes the scan walk only that type's vectors. For the
planner to match the partial index the retriever renders the entity type as a **literal**, not a
bind parameter.

Reading a bounded window from the index also needs `hnsw.iterative_scan = relaxed_order`, which the
engine applies with `SET LOCAL` for the duration of each search transaction. Without it the scan
stops at roughly `ef_search` rows regardless of the requested limit. The setting arrived in
**pgvector 0.8**; on older versions Postgres rejects it, and because each setting is applied inside
its own savepoint the search still runs, just over a smaller candidate window.

The migration that creates these also creates the `uuid-ossp`, `ltree`, `unaccent`, `pg_trgm` and
`vector` extensions, unless `vector` already exists and `LLM_FORCE_EXTENSION_MIGRATION` is off.

### Ranking formulas

#### Fuzzy ranking

Fuzzy search splits the query on whitespace, removes case-insensitive duplicates, and ignores
punctuation-only terms. Identifiers such as UUIDs and IP prefixes stay intact. If no terms remain,
the original query is used as one term. Searchable field types are `string`, `uuid`, `block` and
`resource_type`.

Each term gets its best similarity across the entity's searchable fields. Terms can match in any
order, with words between them, or in different fields. The entity's score is the average of those
best matches. A separate whole-phrase similarity can help an entity qualify, but does not determine
its ranking score:

```text
term_score(term) = max(word_similarity(term, field_value))  # across the entity's searchable fields
score           = round(mean(term_score(term)), 12)       # across the query terms
phrase_score    = max(word_similarity(whole_query, field_value))
```

##### What the three thresholds control

The thresholds are defined on `FuzzyRetriever`. Similarities range from `0` to `1`; higher means a
closer text match.

| Constant | Default | Checked against | Purpose |
| --- | ---: | --- | --- |
| `GATE_THRESHOLD` | `0.5` | A term or the whole query against one searchable field, using `<%` | Finds candidates through the trigram index before scoring all their fields. Passing this gate alone does not guarantee a result. |
| `MIN_TERM_SCORE` | `0.4` | Each term's best similarity anywhere in the entity | Stops a strong phrase match from hiding a term that barely matches or is absent. Applies to multi-term queries. |
| `MIN_SCORE` | `0.6` | The final average term score; also the best whole-phrase similarity for the fallback route | Requires a sufficiently strong overall match. Both checks currently share this value. |

For a multi-term query, an entity must pass both stages:

1. **Candidate selection — either route is enough:** every term passes `'<term>' <% value` in
   at least one searchable field, **or** the whole query passes `<%` and reaches `MIN_SCORE` in
   one field. The second route tolerates a weak term when the surrounding phrase matches well.
2. **Score filtering — both checks must pass:** every term's best similarity reaches
   `MIN_TERM_SCORE`, **and** their average reaches `MIN_SCORE`. These checks apply regardless of
   which route selected the entity.

For a single term, there is only the term gate and the final `MIN_SCORE` check. For example,
`LIR` against `LIP` scores `0.5`: it passes the gate but is excluded because it falls below `0.6`.

`MIN_SCORE` is not just a phrase threshold: it also filters the score returned by the retriever.
Renaming it to `MIN_PHRASE_SCORE` would describe only the fallback check. If these checks need
independent tuning, they can be split into `MIN_PHRASE_SCORE` and `MIN_ENTITY_SCORE`; the current
implementation uses one shared minimum.

With the defaults, `MIN_TERM_SCORE < GATE_THRESHOLD < MIN_SCORE`: the phrase route can admit a
term below the normal gate, but the entity must still have a strong average. Raising
`GATE_THRESHOLD` narrows candidate selection; raising `MIN_TERM_SCORE` makes the phrase route
less tolerant of weak terms; raising `MIN_SCORE` tightens both the final score filter and phrase
admission. Keep `MIN_TERM_SCORE <= GATE_THRESHOLD <= MIN_SCORE` when tuning so the term floor
does not undo the normal gate and the gate does not block otherwise qualifying phrase matches.

##### Worked ranking example

For the query **`ACM LIR`**, assume each entity has only the searchable fields shown below:

| Searchable fields | Best `ACM` | Best `LIR` | Average score | Fuzzy result |
| --- | ---: | ---: | ---: | --- |
| description: `ACM prefix LIR` | 1.0 | 1.0 | **1.0** | Included; tied for highest score. Terms need not be adjacent. |
| customer: `ACM`; description: `LIR` | 1.0 | 1.0 | **1.0** | Included; tied for highest score. Terms can match different fields. |
| description: `ACM LIP` | 1.0 | 0.5 | **0.75** | Included below the exact matches; both terms pass the gate. |
| description: `ACM L2VPN Hillcrest - Meadowbrook` | 1.0 | 0.25 | **0.625** | Excluded: the phrase scores `0.625`, but `LIR` fails `MIN_TERM_SCORE`. |

The last row shows why the per-term floor matters: a good average and a good phrase score are
not enough if one requested term barely matches. Equal fuzzy scores are ordered by entity ID.
These are fuzzy-only results; hybrid search can still return excluded entities through its
semantic source.

##### Worked whole-phrase fallback

For the query **`Coffee grinder CG-3000-XS`**, consider an entity whose only searchable field is
the description **`Coffee grinder CG-2000-XL`**. Values below are rounded for display:

| Check | Similarity | Outcome |
| --- | ---: | --- |
| Best match for `Coffee` | 1.0 | Passes the term gate. |
| Best match for `grinder` | 1.0 | Passes the term gate. |
| Best match for `CG-3000-XS` | 0.43 | Fails the `0.5` gate, but clears the `0.4` term floor. |
| Whole query against the description | 0.71 | Passes the phrase gate and the `0.6` minimum, admitting the entity for scoring. |
| Average of the three best term scores | **0.81** | Passes the `0.6` final minimum; the entity is returned with this score. |

The phrase score admits the typo; the average term score determines its rank. By comparison,
`Coffee grinder XYZ` against `Coffee grinder` has a strong phrase score (about `0.79`) and an
average term score of about `0.67`, but `XYZ` scores `0.0`, so the entity is excluded.

##### Query execution and highlights

Candidate selection depends on the number of unique terms:

- **One term**: use its trigram filter directly, without additional term checks.
- **Multiple terms**: start with the first query term and check every term within each matching entity.
  Term order can affect performance: starting with a common term may require checking more entities.
  A `UNION` adds entities with a field that matches the whole phrase.

The `<%` operator reads PostgreSQL's `pg_trgm.word_similarity_threshold`; the engine sets it
through `FuzzyRetriever.GATE_THRESHOLD` before executing the query.
The selected entity IDs are stored in a materialized CTE, then their searchable fields are scored.
For standard queries, we check whether each entity matches the filters.
Other query shapes use a join. The gate threshold is applied with `SET LOCAL`, so it lasts for the
search transaction only; it also applies during hybrid search.

After score filtering, a lateral lookup chooses the field with the highest average term similarity
as the highlight. Ties prefer fewer path levels, then the path itself. Fuzzy results are ordered by
score descending, then entity ID ascending.

#### Semantic ranking

Semantic search considers rows with an embedding; an entity's score is
`1 / (1 + min(embedding <-> query_vector))`, so a smaller distance gives a higher score, bounded
to `[0, 1]`.

It runs one of two plans. Interactive searches take the `SEARCH_SEMANTIC_CANDIDATE_LIMIT` fields
nearest the query embedding straight from the entity type's partial HNSW index, applying the
structured filters *inside* that scan, and rank only those. Ranking within the window is exact;
only which fields enter the window is approximate, and the window bounds how deep pagination can
reach. Exports keep the exhaustive plan, which scores every embedded field of every candidate:
an export is a single query, without a cursor, for up to 10000 entities,
and a window of 2000 fields can never yield that many.

#### Structured ranking

Structured search has no relevance ranking (`score = 1.0`); results are ordered by an optional
`order_by` field materialized from the index rows.

#### Hybrid ranking

Hybrid search uses **Reciprocal Rank Fusion (RRF)**: rather than trying to make a distance and a
similarity score comparable, it ranks results separately by each signal and combines the *ranks*.

It runs the fuzzy and the semantic retriever on the same candidates, each producing one row per
entity with its score and the field to highlight, and fuses the two rankings:

- the **fuzzy retriever** uses the per-term matching rules and average score described above;
- the **semantic retriever** ranks the entities in its bounded window (the
  `SEARCH_SEMANTIC_CANDIDATE_LIMIT` fields closest to the query embedding, read from that entity
  type's HNSW index), or every embedded entity when the query is an export or asks for more entities
  than the window holds, exactly as it does on its own.

Each side is dense-ranked on its own (equal scores share a rank). Equal fuzzy scores are ordered by
the depth of the matching path, so an entity whose own description matches ranks above entities that
carry the same text in a nested block. The two rankings are joined with a full outer join, so an
entity found by only one retriever still gets a score and the missing side contributes `0`.
Queries with no qualifying fuzzy matches therefore come out in the semantic order, while
identifiers and names that meet the fuzzy thresholds are lifted. Adding a term that matches no
searchable field excludes an entity from the fuzzy results; it can still appear through semantic
retrieval. The reported matching field is the fuzzy retriever's when there is one, otherwise
the semantic retriever's.

```text
perfect = 1 if best_fuzzy_score >= 0.9 else 0
w_sem   = (k+1)/((k+R)(k+R+1)) if perfect else 1  # R = 1000: semantics only break ties between perfect matches
rrf     = w_sem/(k + sem_rank) + 1/(k + fuzzy_rank)   # k = 60; a NULL rank contributes 0
rrf_max = n_sources / (k + 1)                     # n_sources = 2
beta    = rrf_max * 1.05
score   = (rrf + beta * perfect) / (beta + rrf_max)   # normalized to [0, 1]
```

For indexed fields, `best_fuzzy_score` is the average of the best per-term similarities.
Process searches use the higher of this score and the last-step score described above.
Because `beta` exceeds the largest possible `rrf`, any near-exact text match (fuzzy
score ≥ 0.9) always outranks every non-perfect result, including entities that only semantic
ranking would have put on top. Among perfect matches the text decides: the semantic term is scaled
down so far that it cannot overturn a fuzzy-rank difference for the first `R = 1000` rank levels
(identical similarities share a rank, so real queries stay far below that), and only orders entities
with the same fuzzy score and matching depth. Ties break on `entity_id`.

Because the semantic retriever always contributes its window, a lookup query is followed by its
semantic neighbours: `has_next_page` stays true after the last text match, and an export includes
the neighbours up to its limit. Without an embedding (a UUID, or an embedder that produced none) the
process hybrid runs its fuzzy side alone and normalises with one source, so a perfect match then
scores `1.0` instead of about `0.76`.

### Filters

Structured filtering is a typed tree:

- A **`PathFilter`** is one predicate over one path, written as
  `{path, condition, value_kind}`. It adds a type guard so a numeric filter can never match a
  string row. A dotless path such as `status` matches any path *ending* in that component; a
  dotted path must match exactly.
- A **`FilterTree`** nests `PathFilter`s under `AND` / `OR`, up to five levels deep. Each leaf
  compiles to a correlated `EXISTS (SELECT 1 FROM ai_search_index WHERE entity_id = ... AND ...)`;
  `not_has_component` compiles to `NOT EXISTS`.

Condition types are a union tried in order: date (timestamp casts, half-open `between`), numeric
(bigint/double casts), string (`ilike`, wildcard required), contains (POSIX `~*`), `ltree`
(`matches_lquery`, `is_ancestor`, `is_descendant`, `has_component`, `ends_with`), and equality
(`eq`/`neq`, case-insensitive, boolean-aware) last as the most general.

Requests may also send an Elasticsearch-style DSL, which is converted to a `FilterTree`.

`GET /api/search/definitions` returns the valid operators and value schemas for each UI type,
the `value_kind` a filter declares. Read it from there rather than from this page: it is generated
from the same definitions the query builder uses.

### Query types and persistence

A search is one of four typed query objects:

| Query            | Purpose                                   | Limit    |
|------------------|-------------------------------------------|----------|
| `SelectQuery`    | return matching entities                  | ≤ 100    |
| `ExportQuery`    | bulk export matching entities             | ≤ 10 000 |
| `CountQuery`     | count, optionally grouped                 | n/a      |
| `AggregateQuery` | `COUNT`/`SUM`/`AVG`/`MIN`/`MAX` over matches | n/a   |

Counts and aggregations need field values as columns, so the engine pivots the EAV rows with
`MAX(CASE WHEN path = :p THEN value END)` grouped by `entity_id`. The same pivot powers inline
`response_columns` on search results, temporal grouping (`date_trunc`) and cumulative window sums.

Before any SQL runs, queries are validated against the live index: lquery syntax, whether the
referenced paths exist, whether the filter matches the field's type, and grouping and aggregation
constraints.

### The distinct-paths table

A filter UI needs to know which fields are queryable for an entity type, so it can offer
autocomplete and render the right control per field. That is what `GET /api/search/paths`
(GraphQL `searchPaths`, agent tool `discover_filter_paths`) answers.

Deriving that list by grouping `ai_search_index` on every request is slow, because the work scales
with the number of entities rather than with the schema. The distinct paths are therefore
materialized in a small companion table, `ai_search_paths`:

| Column        | Description                                                                     |
|---------------|---------------------------------------------------------------------------------|
| `entity_type` | `SUBSCRIPTION` / `PRODUCT` / `PROCESS` / `WORKFLOW`                              |
| `path`        | the `ltree` field path, e.g. `subscription.node.name`                            |
| `value_type`  | the field's type, used to pick the UI control                                    |
| `refcount`    | how many `ai_search_index` rows currently carry this `(entity_type, path, value_type)` |

The primary key is `(entity_type, path, value_type)`, so there is exactly one row per distinct
path, typically a few thousand against millions of index rows. The endpoint filters this table
by `entity_type`, matches an optional `ltree` prefix, and can rank the result by trigram
similarity to a search term, so it stays fast no matter how many subscriptions exist.

Unlike `subscriptions_search`, this table is never bulk-refreshed. A row trigger on
`ai_search_index`, `ai_search_paths_maintain_trg`, keeps it exact: inserts increment a tuple's
`refcount`, deletes decrement it and drop the row at zero, and updates move one count from the old
tuple to the new one only when the tuple actually changes. Re-indexing a changed *value* is a
no-op for this table.

```sql
SELECT tgname, tgenabled FROM pg_trigger WHERE tgname = 'ai_search_paths_maintain_trg';
```

Run `python main.py index rebuild-paths` to recompute the table if it drifts, for example after a
manual `TRUNCATE ai_search_index`, which (unlike `DELETE`) does not fire the trigger.

!!! note

    `ai_search_paths` was added by migration `ca79fd834ba0`. Installations below that revision do
    not have it, and `GET /api/search/paths` fails until they migrate.

### Empty-result broadening for the agent tool

The agent `search` tool runs a broadening waterfall rather than returning nothing. It first runs
the query as asked; if that returns no rows and free text is present, it retries with
progressively looser filters:

1. drop loose `like` filters, keep high-signal `eq`, range and component filters;
2. drop all filters.

Broadening is on by default; a request turns it off with `allow_fallback: false` to get an exact
answer. The first rung is skipped when it would be pointless (nothing loose to drop, or nothing
high-signal to keep), and an unfiltered search is never retried. The retriever never changes: the hybrid
retriever fuses the fuzzy and the semantic ranking, so with an embedding an empty result can only
mean the filters matched nothing, and a forced retriever stays forced. The query text is embedded
once and reused by every rung. The response reports which retriever produced the results and
whether broadening was used.

### Settings

All embedding settings live in `LLMSettings` (`orchestrator/core/settings.py`).

| Setting                                 | Default                          | Purpose                                                    |
|-----------------------------------------|----------------------------------|------------------------------------------------------------|
| `EMBEDDING_API_ENABLED`                 | `False`                          | master switch; when off, search is fuzzy and structured only |
| `EMBEDDING_MODEL`                       | `openai/text-embedding-3-small`  | LiteLLM model id, in `provider/model` form                  |
| `EMBEDDING_DIMENSION`                   | `1536`                           | vector size (100 to 2000); baked into the column type          |
| `EMBEDDING_API_KEY` / `EMBEDDING_API_BASE` | `""` / `None`                 | credentials and endpoint                                    |
| `EMBEDDING_ENCODING_FORMAT`             | `float`                          | LiteLLM encoding format                                     |
| `EMBEDDING_SAFE_MARGIN_PERCENT`         | `0.1`                            | token-budget headroom per embedding batch                   |
| `EMBEDDING_FALLBACK_MAX_TOKENS`         | `512`                            | context window to assume when the model's is unknown        |
| `EMBEDDING_MAX_BATCH_SIZE`              | `None`                           | maximum items per embedding batch (`None` = unlimited)      |
| `LLM_MAX_RETRIES` / `LLM_TIMEOUT`       | `3` / `30`                       | LiteLLM retry and timeout, used during indexing             |
| `LLM_FORCE_EXTENSION_MIGRATION`         | `False`                          | force `CREATE EXTENSION` in the search migration            |
| `SEARCH_SEMANTIC_CANDIDATE_LIMIT`       | `2000`                           | fields the semantic retriever, and the hybrid retriever's semantic source, read from the HNSW index per search; bounds how deep pagination reaches |

Live queries do not use `LLM_MAX_RETRIES`/`LLM_TIMEOUT`: they embed with a 5-second timeout and no
retries, because a slow search is worse than one without semantic ranking.

The only related `AppSettings` flag is `MCP_ENABLED` (default `False`), which mounts `/mcp`.

### Where the code lives

| Area                                             | Location                                                              |
|--------------------------------------------------|-----------------------------------------------------------------------|
| Traversal, change detection, embedding, upsert     | `orchestrator/core/search/indexing/`                                  |
| Query objects, validation, SQL building, persistence | `orchestrator/core/search/query/`                                   |
| Retrievers and pagination                          | `orchestrator/core/search/retrieval/`                                 |
| Filter tree and operator definitions               | `orchestrator/core/search/filters/`                                   |
| Field types and the embedding client               | `orchestrator/core/search/core/`                                      |
| Agent broadening waterfall                         | `orchestrator/core/search/fallback.py`                                |
| REST endpoints                                     | `orchestrator/core/api/api_v1/endpoints/search.py` and `mcp_tools.py` |
| GraphQL resolvers                                  | `orchestrator/core/graphql/resolvers/search.py`                       |
| CLI commands                                       | `orchestrator/core/cli/search/`                                       |
| Tables                                             | `orchestrator/core/db/models.py`                                      |
| Migrations                                         | `orchestrator/core/migrations/versions/schema/` (`262744958e0c`, `ca79fd834ba0`) |

For the reasoning behind this design, see
[PostgreSQL hybrid search](https://timfrohlich.com/blog/postgresql-hybrid-search).
