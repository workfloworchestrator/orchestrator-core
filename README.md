# Orchestrator-Core
[![codecov](https://codecov.io/gh/workfloworchestrator/orchestrator-core/branch/main/graph/badge.svg?token=5ANQFI2DHS)](https://codecov.io/gh/workfloworchestrator/orchestrator-core)

This is the orchestrator core repository

## Installation

Step 1:
```bash
pip install flit
```

Step2:
```bash
flit install --deps develop --symlink
```

## Running tests.

Create a database

```bash
createuser -s -P nwa
createdb orchestrator-core-test -O nwa
```

Run tests
```bash
pytest test/unit_tests
```
