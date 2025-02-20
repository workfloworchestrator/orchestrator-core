# Orchestrator-Core
[![Downloads](https://pepy.tech/badge/orchestrator-core/month)](https://pepy.tech/project/orchestrator-core)
[![codecov](https://codecov.io/gh/workfloworchestrator/orchestrator-core/branch/main/graph/badge.svg?token=5ANQFI2DHS)](https://codecov.io/gh/workfloworchestrator/orchestrator-core)
[![pypi_version](https://img.shields.io/pypi/v/orchestrator-core?color=%2334D058&label=pypi%20package)](https://pypi.org/project/orchestrator-core)
[![Supported python versions](https://img.shields.io/pypi/pyversions/orchestrator-core.svg?color=%2334D058)](https://pypi.org/project/orchestrator-core)
![Discord](https://img.shields.io/discord/1295834294270558280?style=flat&logo=discord&label=discord&link=https%3A%2F%2Fdiscord.gg%2FKNgF6gE8)

<p style="text-align: center"><em>Production ready Orchestration Framework to manage product lifecycle and workflows. Easy to use, Built on top of FastAPI</em></p>


## Documentation
Can be found [here](https://workfloworchestrator.org/orchestrator-core/)

## Usage
This project can be installed as follows:

#### Step 1:
Install the core.
```shell
pip install orchestrator-core
```

#### Step 2:
Create a postgres database:
```shell
createuser -sP nwa
createdb orchestrator-core -O nwa
```

#### Step 3 (optional):
When using multiple workers, you will need a redis server for live updates with websockets.

By default it will use memory which works with only one worker.
```shell
export WEBSOCKET_BROADCASTER_URL="memory://"
```

For the redis connection you need to set the env variable with the connection url.
```shell
export WEBSOCKET_BROADCASTER_URL="redis://localhost:6379"
```


Websockets can also be turned off with:
```shell
export ENABLE_WEBSOCKETS=False
```

If you want to use pickle for CACHE serialization you will need to set the `CACHE_HMAC_SECRET`:
```shell
export CACHE_HMAC_SECRET="SOMESECRET"
```
**NOTE**: The key can be any length. However, the recommended size is 1024 bits.

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

#### Step 5 (Optional):
OrchestratorCore comes with a graphql interface that can to be registered after you create your OrchestratorApp.
If you add it after registering your `SUBSCRIPTION_MODEL_REGISTRY` it will automatically create graphql types for them.
More info can be found in `docs/architecture/application/graphql.md`

example:
```python
from orchestrator import OrchestratorCore
from orchestrator.settings import AppSettings

app = OrchestratorCore(base_settings=AppSettings())
# register SUBSCRIPTION_MODEL_REGISTRY
app.register_graphql()
```

#### Step 6:
Initialize the migration environment.
```shell
PYTHONPATH=. python main.py db init
PYTHONPATH=. python main.py db upgrade heads
```

### Step 7:
Profit :)

Authentication and authorization are default enabled, to disable set `OAUTH2_ACTIVE` and `OAUTH2_AUTHORIZATION_ACTIVE` to `False`.

```shell
uvicorn --reload --host 127.0.0.1 --port 8080 main:app
```

Visit [http://127.0.0.1:8080/api/redoc](http://127.0.0.1:8080/api/redoc) to view the api documentation.


## Setting up a development environment

To add features to the repository follow the following procedure to setup a working development environment.

### Installation (Development standalone)
Install the project and its dependencies to develop on the code.

#### Step 1 - install flit:

```shell
python3 -m venv venv
source venv/bin/activate
pip install flit
```

#### Step 2 - install the development code:

!!! danger
    Make sure to use the flit binary that is installed in your environment. You can check the correct
    path by running
    ```shell
    which flit
    ```

To be sure that the packages will be installed against the correct venv you can also prepend the python interpreter
that you want to use:

```shell
flit install --deps develop --symlink --python venv/bin/python
```


### Running tests
Run the unit-test suite to verify a correct setup.

#### Step 1 - Create a database

```shell
createuser -sP nwa
createdb orchestrator-core-test -O nwa
```

#### Step 2 - Run tests
```shell
pytest test/unit_tests
```
or with xdist:

```shell
pytest -n auto test/unit_tests
```

If you do not encounter any failures in the test, you should be able to develop features in the orchestrator-core.

### Installation (Development symlinked into orchestrator SURF)

If you are working on a project that already uses the `orchestrator-core` and you want to test your new core features
against it, you can use some `flit` magic to symlink the dev version of the core to your project. It will
automatically replace the pypi dep with a symlink to the development version
of the core and update/downgrade all required packages in your own orchestrator project.

#### Step 1 - install flit:

```shell
python - m venv venv
source venv/bin/activate
pip install flit
```

### Step 2 - symlink the core to your own project

```shell
flit install --deps develop --symlink --python /path/to/a/orchestrator-project/venv/bin/python
```

So if you have the core and your own orchestrator project repo in the same folder and the main project folder is
`orchestrator` and you want to use relative links, this will be last step:

```shell
flit install --deps develop --symlink --python ../orchestrator/venv/bin/python
```

# Increasing the version number for a (pre) release.

When your PR is accepted you will get a version number.

You can do the necessary change with a clean, e.g. every change committed, branch:

```shell
bumpversion patch --new-version 0.4.1-rc3
```

### Changing the Core database schema
When you would like to change the core database schema, execute the following steps.

- Create the new model `orchestrator/database/models.py`
- `cd orchestrator/migrations`
- `alembic revision --autogenerate -m "Name of the migratioin"`
