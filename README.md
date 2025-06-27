# Orchestrator-Core

[![Downloads](https://pepy.tech/badge/orchestrator-core/month)](https://pepy.tech/project/orchestrator-core)
[![codecov](https://codecov.io/gh/workfloworchestrator/orchestrator-core/branch/main/graph/badge.svg?token=5ANQFI2DHS)](https://codecov.io/gh/workfloworchestrator/orchestrator-core)
[![pypi_version](https://img.shields.io/pypi/v/orchestrator-core?color=%2334D058&label=pypi%20package)](https://pypi.org/project/orchestrator-core)
[![Supported python versions](https://img.shields.io/pypi/pyversions/orchestrator-core.svg?color=%2334D058)](https://pypi.org/project/orchestrator-core)
![Discord](https://img.shields.io/discord/1295834294270558280?style=flat&logo=discord&label=discord&link=https%3A%2F%2Fdiscord.gg%2FKNgF6gE8)

<p style="text-align: center"><em>Production ready Orchestration Framework to manage product lifecycle and workflows. Easy to use, built on top of FastAPI and Pydantic</em></p>

## Documentation

The documentation can be found at [workfloworchestrator.org](https://workfloworchestrator.org/orchestrator-core/).

## Installation (quick start)

Simplified steps to install and use the orchestrator-core.
For more details, read the [Getting started](https://workfloworchestrator.org/orchestrator-core/getting-started/base/) documentation.

### Step 1 - Install the package

Create a virtualenv and install the orchestrator-core.

```shell
python -m venv .venv
source .venv/bin/activate
pip install orchestrator-core
```

### Step 2 - Setup the database

Create a postgres database:

```shell
createuser -sP nwa
createdb orchestrator-core -O nwa  # set password to 'nwa'
```

Configure the database URI in your local environment:

```
export DATABASE_URI=postgresql://nwa:nwa@localhost:5432/orchestrator-core
```

### Step 3 - Create main.py

Create a `main.py` file.

```python
from orchestrator import OrchestratorCore
from orchestrator.cli.main import app as core_cli
from orchestrator.settings import AppSettings

app = OrchestratorCore(base_settings=AppSettings())

if __name__ == "__main__":
    core_cli()
```

### Step 4 - Run the database migrations

Initialize the migration environment and database tables.

```shell
python main.py db init
python main.py db upgrade heads
```

### Step 5 - Run the app

```shell
export OAUTH2_ACTIVE=False
uvicorn --reload --host 127.0.0.1 --port 8080 main:app
```

Visit the [ReDoc](http://127.0.0.1:8080/api/redoc) or [OpenAPI](http://127.0.0.1:8080/api/docs) page to view and interact with the API.

## Contributing

We use [uv](https://docs.astral.sh/uv/getting-started/installation/) to manage dependencies.

To get started, follow these steps:

```shell
# in your postgres database
createdb orchestrator-core-test -O nwa  # set password to 'nwa'

# on your local machine
git clone https://github.com/workfloworchestrator/orchestrator-core
cd orchestrator-core
export DATABASE_URI=postgresql://nwa:nwa@localhost:5432/orchestrator-core-test
uv sync --all-extras --all-groups
uv run pytest
```

For more details please read the [development docs](https://workfloworchestrator.org/orchestrator-core/contributing/development/).
