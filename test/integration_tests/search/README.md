# Search Integration Tests

Integration tests and benchmarking for search functionality.

## Run Integration Tests

```bash
SEARCH_ENABLED=true uv run pytest test/integration_tests/search/
```

## Record Ground Truth

Generate baseline embeddings and rankings:

```bash
SEARCH_ENABLED=true uv run pytest test/integration_tests/search/ --record
```

**When to regenerate:**

- After modifying test data in `fixtures.py`
- After changing the baseline embedding model
- After updating search algorithms

## Run Benchmark

Compare embedding models against baseline:

```bash
SEARCH_ENABLED=true uv run pytest test/integration_tests/search/ --benchmark
```

**Configure models** by editing `data/models.json`
