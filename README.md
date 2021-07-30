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

You can develop on the core in 2 ways; as a standalone project, or if you build a project that uses the pypi package
of the core you can use a cool symlink trick to get 2 editable projects.

### Step 1:
Install flit:

```bash
python3 -m venv venv
source venv/bin/activate
pip install flit
```

### Step 2:
This step depends on where you want to install the core; there are two possibilities: standalone (e.g. to run tests)
or symlinked to an orchestrator-project that you're working on.

*Stand alone*

```bash
flit install --deps develop --symlink --python venv/bin/python
# optional: handy for tests and development
pip install redis
pip install pre-commit
```

*Symlinked to other orchestrator-project*

You can point the last parameter to the python binary in the venv you're using for your own orchestrator project.
It will automatically replace the pypi dep with a symlink to the development version of the core and update/downgrade
all required packages in your own orchestrator project.

```bash
flit install --deps develop --symlink --python /path/to/a/orchestrator-project/venv/bin/python
```

So if you have the core and your own orchestrator project repo in the same folder and the main project folder is
`orchestrator` and want to use relative links:

```bash
flit install --deps develop --symlink --python ../orchestrator/venv/bin/python
```

Note: When you change requirements you can just re-execute "Step 2".

## Running tests.

*Create a database*

```bash
createuser -sP nwa
createdb orchestrator-core-test -O nwa
```

*Run tests*

```bash
pytest test/unit_tests
```

or with xdist:

```bash
pytest -n auto test/unit_tests
```
