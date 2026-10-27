# Search benchmark

Measures whether a change to the text search (the fuzzy retriever) makes results better or worse, and what it costs
Postgres. Semantic and hybrid retrieval are out of scope: they depend on the embedding model and its size.

Accuracy is scored against *labels*, not against recorded output of the engine, so a wrong result is not locked in as
correct. Performance is the `EXPLAIN (ANALYZE, BUFFERS)` plan of each query, never wall time.

## How it works

1. `corpus.py` + `profiles/generic.py`: a seeded corpus of network services (ports, light paths, L2VPNs, IP peerings)
   with nested blocks and lists, confusable locations, neighbouring node names and customers on several services. The
   same profile, seed and size give the same corpus; nothing large is committed.
2. The corpus is indexed through the real `Indexer` into `ai_search_index`, in a database built by the real Alembic
   migrations (the integration test fixtures, `pgvector/pgvector:pg15` and `pg17` in CI).
3. Queries: ~30 hand-written ones (`queries/handwritten.yaml`, each with a note on the intended behaviour) plus
   generated ones (`perturb.py`: typo, prefix, reorder, case/punctuation, exact, identifier, customer). They run
   through `execute_search` with `retriever=fuzzy`.
4. Metrics per category (`metrics.py`): MRR, Success@1, Recall@10, and the false-positive rate of `negative` queries.
   Recall@10 is the share of what fits in 10 results, so a query that matches hundreds of entities can reach 1.0.
5. Plan metrics per query (`test.integration_tests.search.performance._plans`): cost, blocks, rows, loops, filtered
   rows and function calls, plus a check that the trigram index is used and `ai_search_index` is never sequentially
   scanned.

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
names and customer-family/location pairs), or the label is incomplete and the metrics measure tie-breaking.
