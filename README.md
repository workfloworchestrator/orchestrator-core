# Orchestrator-Core
[![Downloads](https://pepy.tech/badge/orchestrator-core/month)](https://pepy.tech/project/orchestrator-core)
[![codecov](https://codecov.io/gh/workfloworchestrator/orchestrator-core/branch/main/graph/badge.svg?token=5ANQFI2DHS)](https://codecov.io/gh/workfloworchestrator/orchestrator-core)
[![pypi_version](https://img.shields.io/pypi/v/orchestrator-core?color=%2334D058&label=pypi%20package)](https://pypi.org/project/orchestrator-core)

<p align="center"><em>Production ready Orchestration Framework to manage product lifecyle and workflows. Easy to use, Built on top of FastAPI</em></p>


## Documentation
Can be found [here](https://workfloworchestrator.org/orchestrator-core/)

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

#### Step 3 (optional):
When using multiple workers, you will need a redis, postgres or kafka service for live updates with websockets.
Redis is installed by default and for postgres or kafka you will need to install them:
```bash
pip install broadcaster[postgres]
pip install broadcaster[kafka]
```

For the connection you need an env variable with the connection url.
```bash
export WEBSOCKET_BROADCASTER_URL="redis://localhost:6379"
```

more broadcaster info [here](https://pypi.org/project/broadcaster/)

#### Step 4:
Create a `main.py` file.

```python
from orchestrator import OrchestratorCore
from orchestrator.cli.main import app as core_cli
from orchestrator.settings import AppSettings

app = OrchestratorCore(base_settings=AppSettings())

if __name__ == "__main__":
    core_cli()
```

#### Step 5:
Initialize the migration environment.
```bash
PYTHONPATH=. python main.py db init
PYTHONPATH=. python main.py db upgrade heads
```

### Step 6:
Profit :)

```bash
uvicorn --reload --host 127.0.0.1 --port 8080 main:app
```

Visit [http://127.0.0.1:8080/api/redoc](http://127.0.0.1:8080/api/redoc) to view the api documentation.


## Setting up a development environment

To add features to the repository follow the following procedure to setup a working development environment.

### Installation (Development)
Install the project and its dependancies to develop on the code.

#### Step 1 - install flit:
``` shell
mkdvirtualenv -p python3.9 orchestrator-core
workon orchestrator-core
pip install flit
```

#### Step 2 - install the development code:
``` shell
flit install --deps develop --symlink
```

!!! danger
    Make sure to use the flit binary that is installed in your environment. You can check the correct
    path by running
    ``` shell
    which flit
    ```

### Running tests
Run the unit-test suite to verify a correct setup.

#### Step 1 - Create a database

``` shell
createuser -sP nwa
createdb orchestrator-core-test -O nwa
```

#### Step 2 - Run tests
``` shell
pytest test/unit_tests
```

If you do not encounter any failures in the test, you should be able to develop features in the orchestrator-core.
