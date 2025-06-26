# Base application

By following these steps you can start a bare orchestrator application that can be used to run workflows. This
app runs as a standalone API with workflows loaded that can be run in the background. Similar to a Framework like FastAPI,
Flask and Django, you install the core library, initialise it with configuration and run. The orchestrator-core contains:

* API
* Workflow engine
* Database


!!! note
    The Orchestrator-core is designed to be installed and extended just like a FastAPI or Flask application. For more
    information about how this works read the [Reference documentation](../reference-docs/app/app.md).


### Step 1 - Install the package:

Create a virtualenv and install the core.

<div class="termy">

```shell
python -m venv .venv
source .venv/bin/activate
pip install orchestrator-core
```

</div>

### Step 2 - Setup the database:

Create a postgres database:

<div class="termy">

```shell
createuser -sP nwa
createdb orchestrator-core -O nwa
```

</div>

Choose a password and remember it for later steps.

As an example, you can run these docker commands in separate shells to start a temporary postgres instance:

```shell
docker run --rm --name temp-orch-db -e POSTGRES_PASSWORD=rootpassword -p 5432:5432 postgres:15

docker exec -it temp-orch-db su - postgres -c 'createuser -sP nwa && createdb orchestrator-core -O nwa'
```

### Step 3 - Create the main.py:

Create a `main.py` file.

```python
from orchestrator import OrchestratorCore
from orchestrator.cli.main import app as core_cli
from orchestrator.settings import AppSettings

app = OrchestratorCore(base_settings=AppSettings())

if __name__ == "__main__":
    core_cli()
```

### Step 4 - Run the database migrations:

Initialize the migration environment and database tables.

<div class="termy">

```shell
export DATABASE_URI=postgresql://nwa:PASSWORD_FROM_STEP_2@localhost:5432/orchestrator-core

python main.py db init
python main.py db upgrade heads
```

</div>

### Step 5 - Run the app

<div class="termy">

```shell
export DATABASE_URI=postgresql://nwa:PASSWORD_FROM_STEP_2@localhost:5432/orchestrator-core
export OAUTH2_ACTIVE=False

uvicorn --reload --host 127.0.0.1 --port 8080 main:app
```

</div>

### Step 6 - Profit :boom: :grin:

Visit the [ReDoc](http://127.0.0.1:8080/api/redoc) or [OpenAPI](http://127.0.0.1:8080/api/docs) to view and interact with the API.
