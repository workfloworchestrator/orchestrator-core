# Fast `/api/search/paths` via a trigger-maintained distinct-paths table

**Date:** 2026-07-15
**Status:** Design — approved approach, pending spec review
**Issue:** [#1788 — Slow DB Query](https://github.com/workfloworchestrator/orchestrator-core/issues/1788) (Sentry ORCHESTRATOR-94; offending span is exactly the `/paths` `SELECT ai_search_index.path, ...` `GROUP BY` below). The fix commit / PR must reference `#1788`.

## Problem

`GET /api/search/paths` (and its GraphQL twin `resolve_search_paths` and the MCP
`discover_filter_paths` tool) powers the structured-search UI's field autocomplete.
It returns the set of *queryable field paths* for an entity type — a schema-sized
list (~thousands of distinct `(path, value_type)` tuples).

Today it derives that list live from `ai_search_index`:

```sql
SELECT path, value_type
FROM ai_search_index
WHERE entity_type = :entity_type
  [AND path ~ CAST(:pattern AS lquery)]   -- when a prefix is given
GROUP BY path, value_type
ORDER BY [similarity(path::text, :q) DESC,] path
LIMIT :limit;                             -- limit ∈ [1,10]
```

`ai_search_index` is an EAV table: **one row per entity per field path**, so it holds
hundreds of thousands to millions of rows. The query `GROUP BY`s that entire matched
row set down to a handful of distinct pairs. The output is ≤10 rows, but the work
scales with the whole table — that is the slowness. The `q` branch is worse: it
computes a trigram `similarity()` per grouped row and sorts, with no supporting index
(the trigram GIN index is on `value`, not `path`).

## Chosen approach

Maintain a small **summary table** `ai_search_paths` holding exactly the distinct
tuples, kept in sync by a Postgres **row trigger** on `ai_search_index` that keeps a
reference count per tuple. `build_paths_query` reads this table instead of the EAV
table, so `/paths` scans a few-thousand-row table and returns instantly. A
`rebuild_search_paths()` recompute provides drift recovery and a fast path for the
rare full-wipe / full-reindex maintenance operations.

### Why this over the alternatives

- **Plain `VIEW`** — rejected. A view re-runs the same `DISTINCT` scan on every read;
  no speedup. The result must be *stored*.
- **Materialized view + refresh-after-indexing** — viable; zero drift, deletes/wipes
  handled for free. Rejected in favour of the trigger because it re-scans the whole
  EAV table at every refresh, and the user prefers a self-maintaining DB-native object
  with no Python hook in the indexing path.
- **Trigger that `REFRESH`es a matview** — impossible. `REFRESH ... CONCURRENTLY`
  cannot run inside a transaction (a trigger always runs inside the triggering
  statement's transaction), and a non-concurrent refresh per bulk-write statement is
  O(table) repeated thousands of times per reindex.
- **Trigger-maintained refcount table (chosen)** — always fresh, cheap on the common
  per-subscription path, needs only a table + trigger. Its costs (see Risks) fall on
  rare maintenance ops and are addressed by `rebuild_search_paths()`.

## Components

### 1. Table `ai_search_paths`

| column | type | notes |
|---|---|---|
| `entity_type` | `TEXT NOT NULL` | |
| `path` | `LTREE NOT NULL` | |
| `value_type` | `field_type NOT NULL` | reuse existing enum |
| `refcount` | `INTEGER NOT NULL` | number of `ai_search_index` rows with this tuple |

Primary key: `(entity_type, path, value_type)`.

Indexes: **PK only** for the MVP. The PK btree covers the `entity_type = :x` filter and
the `ORDER BY path`. The `path ~ lquery` prefix match seq-scans a schema-sized table
(~thousands of rows) in well under a millisecond.
`# ponytail: no GIST/btree on path; table is schema-sized, seq scan is instant. Add gist_ltree_ops(path) if it grows large.`

A matching SQLAlchemy model `AiSearchPaths` is added to `orchestrator/core/db/models.py`,
mirroring `AiSearchIndex`'s column types (`LtreeType`, the `field_type` `Enum`).

### 2. Trigger on `ai_search_index`

`AFTER INSERT OR UPDATE OR DELETE ... FOR EACH ROW`, PL/pgSQL function branching on
`TG_OP`. The base table's upsert is `INSERT ... ON CONFLICT (entity_id, path) DO UPDATE`,
which correctly fires the **INSERT** trigger on a genuinely new row and the **UPDATE**
trigger on conflict — so `TG_OP` reflects reality.

- **INSERT** → `INSERT INTO ai_search_paths (...) VALUES (NEW.entity_type, NEW.path, NEW.value_type, 1) ON CONFLICT (entity_type, path, value_type) DO UPDATE SET refcount = ai_search_paths.refcount + 1`
- **DELETE** → decrement the `OLD` tuple's refcount; delete the row when it reaches 0.
- **UPDATE** → only act `WHEN (OLD.entity_type, OLD.path, OLD.value_type) IS DISTINCT FROM (NEW.entity_type, NEW.path, NEW.value_type)`: decrement the OLD tuple (delete if 0), increment the NEW tuple. A re-index that doesn't change the tuple (same `value_type`) is a no-op — no refcount churn.

Returns `NULL` (AFTER row trigger; return value ignored).

The trigger keeps the table **exact under every current write path**: streaming
upserts, mid-index stale-path deletes (`_execute_batched_deletes`), process-cleanup
deletes (`cleanup_ai_search_index`), and the full `DELETE FROM ai_search_index` on
embedding resize (`drop_all_embeddings`) — all are row-level DML that fire the trigger.

### 3. `rebuild_search_paths()` recompute

A small Python service function (visible, testable, wireable) that recomputes the
table from ground truth in one pass:

```sql
TRUNCATE ai_search_paths;
INSERT INTO ai_search_paths (entity_type, path, value_type, refcount)
SELECT entity_type, path, value_type, count(*)
FROM ai_search_index
GROUP BY entity_type, path, value_type;
```

Roles:
1. **Drift-recovery button** — exposed as a CLI command (alongside the existing
   `search index-llm` commands) to rebuild from truth if a refcount is ever corrupted
   by a bug or manual DB surgery.
2. **Correctness guarantee on the embedding-resize path** — called at the end of the
   resize command so the summary is authoritative in one cheap recompute rather than
   depending on millions of per-row trigger fires.
3. **Shared logic with the migration backfill** (same `INSERT ... SELECT`).

### 4. Query change

`build_paths_query` (`orchestrator/core/search/query/builder.py`) selects
`AiSearchPaths.path, AiSearchPaths.value_type` filtered by `entity_type`, keeps the
`prefix` lquery filter (works unchanged on the new `path` column via `LtreeFilter`),
drops the now-redundant `GROUP BY` (rows are distinct by construction), and keeps the
`q` similarity / plain `path` ordering. `process_path_rows` is unchanged — it still
receives `(path, value_type)` rows. GraphQL and MCP consumers benefit automatically
since they call the same builder.

### 5. Migration

Raw SQL via `op.get_bind()` + `text()` with `IF NOT EXISTS`, matching the existing
`2026-04-13_262744958e0c_add_ai_search_tables.py` style. Within the upgrade transaction:

1. `CREATE TABLE IF NOT EXISTS ai_search_paths (...)` with the PK.
2. `CREATE OR REPLACE FUNCTION` for the trigger + `CREATE TRIGGER` (guarded so re-runs
   don't duplicate).
3. **Backfill** with the `rebuild_search_paths()` `INSERT ... SELECT` so existing
   installations populate their refcounts on deploy. (Backfill writes only
   `ai_search_paths`; it does not touch `ai_search_index`, so it does not fire the
   trigger.)

Downgrade: drop the trigger, the function, and the table.

## Data flow

```
subscription create/modify workflow ─┐
product / process API PATCH          ├─→ run_indexing_for_entity → INSERT/UPDATE/DELETE on ai_search_index
CLI reindex                          ─┘                                   │
                                                          (row trigger, per row)
                                                                          ▼
                                                          ai_search_paths (refcount per tuple)
                                                                          ▲
GET /api/search/paths ── build_paths_query ── SELECT path,value_type ─────┘  (fast, schema-sized scan)

embedding resize / manual recovery ── rebuild_search_paths() ── TRUNCATE + INSERT…SELECT GROUP BY
```

## Error handling & edge cases

- **refcount underflow** — the delete-when-`<= 0` guard removes the row; a negative
  value can only arise from drift and is repaired by `rebuild_search_paths()`.
- **Deleted subscriptions/products/workflows** — the codebase currently only cleans up
  `ai_search_index` rows for deleted *processes*. Orphaned rows for other entity types
  already exist in the base table today; the summary faithfully reflects whatever the
  base table holds. Not in scope to fix here.
- **`value_type` change on re-index** — handled by the UPDATE branch's DISTINCT check.
- **Full wipe (`DELETE FROM ai_search_index`)** — trigger drains refcounts to 0
  (correct); the resize command then calls `rebuild_search_paths()` as the
  authoritative recompute.

## Risks / trade-offs (accepted)

1. **Write-path cost on rare bulk ops.** Per-subscription indexing touches a handful of
   rows → negligible. A full CLI reindex and the resize wipe fire the trigger per row
   (millions of times). Accepted for maintenance ops.
   `# ponytail: follow-up — disable trigger during full reindex/resize + rebuild() once, only if reindex latency is measured to hurt.`
2. **Hot-row contention.** Concurrent indexing of subscriptions sharing a product type
   contends on the same refcount rows. Tolerable at expected write volume; noted.
3. **Trigger invisibility / drift.** The trigger lives in a migration, not Python.
   `rebuild_search_paths()` is the recovery button and a test asserts trigger output
   equals a full recompute.

## Out of scope

- Disabling the trigger during bulk ops (follow-up optimization).
- Extra GIST/btree indexes on `ai_search_paths` (add only if it grows large).
- Cleanup of orphaned `ai_search_index` rows for deleted non-process entities.
- Any change to the `is_lquery_syntactically_valid` validation round-trip.

## Test plan

Trigger behaviour requires a real Postgres → **integration tests**
(`test/integration_tests/search/`). Pure functions → unit tests. Parametrized per
project style.

- **Trigger refcount maintenance** (integration, parametrized cases):
  new tuple → refcount 1; second entity same tuple → 2; delete one of two → 1;
  delete last → row removed; upsert changing `value_type` → old tuple decremented
  (removed if last) + new tuple incremented; re-index with same `value_type` → no
  change; batched multi-row delete → correct decrements.
- **`rebuild_search_paths()`** (integration): corrupt the summary (wrong refcounts,
  spurious/ missing rows), rebuild, assert it equals `SELECT entity_type, path,
  value_type, count(*) ... GROUP BY ...` over the base table.
- **Migration backfill** (integration): after upgrade on a populated
  `ai_search_index`, `ai_search_paths` matches the recompute. (Covered by the rebuild
  test if it shares the assertion helper.)
- **`build_paths_query` regression** (integration/functional): `/api/search/paths`
  returns identical `leaves`/`components` as before for the same fixtures, across
  empty prefix, prefix filter, `q` similarity ordering, each `entity_type`, and the
  `limit` bound. Extend existing endpoint tests; they are the key regression guard.
- **Query source** (unit): compiled `build_paths_query` SQL references
  `ai_search_paths` and no longer `GROUP BY`s.
```
