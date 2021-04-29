# Orchestrator-Core
[![Downloads](https://pepy.tech/badge/orchestrator-core/month)](https://pepy.tech/project/orchestrator-core)
[![codecov](https://codecov.io/gh/workfloworchestrator/orchestrator-core/branch/main/graph/badge.svg?token=5ANQFI2DHS)](https://codecov.io/gh/workfloworchestrator/orchestrator-core)
[![pypi_version](https://img.shields.io/pypi/v/orchestrator-core?color=%2334D058&label=pypi%20package)](https://pypi.org/project/orchestrator-core)

This is the orchestrator core repository

## Usage
This project can be installed as follows:

#### Step 1:
Install the core.
```bash
pip install orchestrator-core
```

#### Step 2:
Create a postgres database:
```bash
createuser -sP nwa
createdb orchestrator-core -O nwa
```

#### Step 3:
Create a `main.py` file.

```python
from orchestrator import OrchestratorCore
from orchestrator.cli.main import app as core_cli
from orchestrator.settings import AppSettings

app = OrchestratorCore(base_settings=AppSettings())

if __name__ == "__main__":
    core_cli()
```

#### Step 4:
Initialize the migration environment.
```bash
PYTHONPATH=. python main.py db init
PYTHONPATH=. python main.py db upgrade heads
```

### Step 5:
Profit :)

```bash
uvicorn --reload --host 127.0.0.1 --port 8080 main:app
```

## Installation (Development)

Step 1:
```bash
pip install flit
```

Step 2:
```bash
flit install --deps develop --symlink
```

## Running tests.

Create a database

```bash
createuser -sP nwa
createdb orchestrator-core-test -O nwa
```

Run tests
```bash
pytest test/unit_tests
```
