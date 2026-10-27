# Search benchmark

Measures whether a change to the text search (the fuzzy retriever) makes results better or worse, and what it costs
Postgres. Semantic and hybrid retrieval are out of scope: they depend on the embedding model and its size.

Accuracy is scored against *labels*, not against recorded output of the engine, so a wrong result is not locked in as
correct. A label is the answer key of a query: the entities it should find (`expected`). Performance is the
`EXPLAIN (ANALYZE, BUFFERS)` plan of each query, never wall time.

## How it works

1. `corpus.py` + `profiles/generic.py`: a seeded corpus of network services (ports, light paths, L2VPNs, IP peerings)
   with nested blocks and lists, confusable locations, neighbouring node names and customers on several services. The
   same profile, seed and size give the same corpus; nothing large is committed.
2. The corpus is indexed through the real `Indexer` into `ai_search_index`, in a database built by the real Alembic
   migrations (the integration test fixtures, `pgvector/pgvector:pg15` and `pg17` in CI).
3. Queries: ~30 hand-written ones (`queries/handwritten.yaml`, each with a note on the intended behaviour) plus
   generated ones (`perturb.py`: typo, prefix, reorder, case/punctuation, exact, identifier, customer plus location).
   They run through `execute_search` with `retriever=fuzzy`.
4. Metrics per category (`metrics.py`): MRR, Success@1, Recall@10, and the false-positive rate of `negative` queries.
   Recall@10 is the share of what fits in 10 results, so a query that matches hundreds of entities can reach 1.0.
5. Plan metrics per query (`test.integration_tests.search.performance._plans`): cost, blocks, rows, loops, filtered
   rows and function calls, plus a check that the trigram index is used and `ai_search_index` is never sequentially
   scanned.

## Anchors

A label is only right if it lists *every* correct answer. Among 3000 random entities, a generated "Bluefin, Amsterdam"
would be a correct answer to `bluefin amsterdam` that the YAML does not know about, and finding it would score as a
miss.

Anchors avoid that: a few hand-designed entities (`anchors()` in the profile) that are always in the corpus, whatever
the seed. Hand-written queries refer to them by key (`expected: [ams-rt10]`), and the generator never produces an
entity that competes with them. Anchors are near-misses of each other (`ams-rt01` against `ams-rt10`, Amsterdam
against Amstelveen), so each query tests one specific distinction. The list is at the top of
`queries/handwritten.yaml`.

## Query categories

| category           | the query is...                                                  | example                                   |
| ------------------ | ---------------------------------------------------------------- | ----------------------------------------- |
| `exact`            | an entity's full description, unchanged                          | `Amsterdam Port ams-rt01 et-0/0/1 for ...` |
| `prefix`           | the description cut off at 60-80%                                | `Amsterdam Port ams-rt01 et-0/0/1 for No` |
| `typo`             | the description with two neighbouring letters swapped            | `Amsterdma Port ams-rt01 ...`             |
| `reorder`          | the description's words shuffled                                 | `Port Northwind ams-rt01 Amsterdam ...`   |
| `case_punctuation` | a node and port in upper case, or without `-` and `/`            | `AMS RT10 ET 0 0 1`                       |
| `identifier`       | a node and port name, IP prefix, ASN or (partial) UUID           | `ams-rt01 et-0/0/1`                       |
| `multi_field`      | a customer plus a location, from different blocks of the entity | `Bluefin University Amsterdam`            |
| `negative`         | text that should find nothing (hand-written only)                | `zxqv blorp`                              |

### Generated queries

`perturb.py` makes queries from the corpus itself, so their labels need no hand-writing:

1. Sample 20 entities with the seed; every category uses the same 20.
2. Per category, join the entity's facts that category uses (`GENERATORS`) and apply its perturbation, as in the table
   above. Queries shorter than 5 characters are dropped.
3. The label is every entity holding the same facts, including the values it only `carries` (a far end), not only the
   entity the query came from.

Labels compare the unperturbed facts: a `prefix` query is only answered by entities with the full description, not by
everything the prefix also matches. All categories draw from one random sequence, so changing `GENERATORS` changes the
queries, and the baseline rows, of the categories after it.

## Reading the accuracy table

All scores run from 0 to 1, averaged over the queries of a category.

- **MRR**: how high the first right answer ranks. 1 at rank 1, 0.5 at rank 2, 0.33 at rank 3, 0 when not found.
- **Success@1**: the share of queries with a right answer on top. Rank 2 counts as a miss.
- **Recall@10**: the share of right answers in the top 10, capped at 10. Is it found at all?
- **false positives**: the share of `negative` queries that returned anything. Lower is better.

High Recall@10 with low Success@1 means search finds the answer but ranks it too low. Plan metrics are explained in
the legend of `baseline/plans.*.md`.

## Reproducibility

Plans only compare when everything else is fixed: the seed and corpus size, `jit = off`,
`max_parallel_workers_per_gather = 0`, `work_mem`, a sorted GiST rebuild, rebuilt indexes and `ANALYZE` over the whole
table (the statistics target is raised until the sample covers every row). `pg_trgm.word_similarity_threshold` is
pinned in `runner.py`; orchestrator-core does not set it, so production uses the server default, and the benchmark
pins that default so it cannot change unseen. Downstream users who change it should change it there too.

`VACUUM` cannot run inside the test transaction; the index is truncated and loaded fresh, so it has no dead rows.

## Run

```bash
uv run pytest test/benchmarks/search            # accuracy + plan baselines, needs Docker for Postgres
uv run pytest test/unit_tests/benchmarks        # the pure parts: corpus, perturbations, metrics, query loader
```

## Update the baselines

The baselines are markdown in `baseline/`, one pair per Postgres major version, so a change reads as a diff:

```bash
uv run pytest test/benchmarks/search --inline-snapshot=fix
git diff test/benchmarks/search/baseline
```

Review the diff per category before committing: an improvement for typos that hurts identifier lookup shows here and
disappears in an average. Commit the files for every Postgres version CI runs (`pg15`, `pg17`); run against each.

## Your own profile

Implement `Profile` from `corpus.py` (`anchors()` and `generate(rng, count)`), keeping hand-written queries in your own
YAML file loaded with `load_handwritten(corpus, path)`. Anchors must not depend on the seed, and `generate` must keep
the facts a hand-written query relies on free of generated entities (the generic profile reserves the anchors' node
names and customer-family/location pairs), or the label is incomplete and the metrics measure tie-breaking. An entity
with several values of one fact (a service with two ends has two identifiers and two locations) lists the others in
`carries`, so that a query for any of them counts the entity as a right answer.
