# Agentic application
!!! danger
    The features and api described in this section are under heavy development and therefore subject to change.
    Be prepared for it to break.

    **However if you don't care about an unstable API, using the features in this mode
    of the orchestrator will unlock quite a bit of potential**


The Agentic mode of the Orchestrator can be unlocked by doing the following.

### Pre-requisites
- pg_vector installed in your postgres database
- At minimum an `api_key` to talk to ChatGPT
- The UI configured to with the LLM integration branch - still WIP - https://github.com/workfloworchestrator/example-orchestrator-ui/pull/72/files

### Step 1 - Install the package:

Create a virtualenv and install the core including the LLM dependencies.

<div class="termy">

```shell
python -m venv .venv
source .venv/bin/activate
pip install orchestrator-core[llm]
```

</div>

### Step 2 - Setup the database:

Create a postgres database, make sure your postgres install has the `pgvector` extension installed:

<div class="termy">

```shell
createuser -sP nwa
createdb orchestrator-core -O nwa
```

</div>

Choose a password and remember it for later steps.

As an example, you can run these docker commands in separate shells to start a temporary postgres instance:

```shell
docker run --rm --name temp-orch-db -e POSTGRES_PASSWORD=rootpassword -p 5432:5432 pgvector/pgvector:pg17

docker exec -it temp-orch-db su - postgres -c 'createuser -sP nwa && createdb orchestrator-core -O nwa'
```

### Step 3 - Create the main.py and wsgi.py:

Create a `main.py` file.
This provides the CLI entrypoint to your Orchestrator.

```python
import typer
from nwastdlib.logging import initialise_logging
from orchestrator import app_settings
from orchestrator.cli.main import app as core_cli
from orchestrator.db import init_database
from orchestrator.log_config import LOGGER_OVERRIDES

def init_cli_app() -> typer.Typer:
    initialise_logging(LOGGER_OVERRIDES)
    init_database(app_settings)
    return core_cli()

if __name__ == "__main__":
    init_cli_app()
```

Create a `wsgi.py` file.
This will be used to run the Orchestrator API.

```python
from orchestrator import AgenticOrchestratorCore
from orchestrator.settings import app_settings
from orchestrator.llm_settings import llm_settings

llm_settings.LLM_ENABLED = True
llm_settings.AGENT_MODEL = 'gpt-4o-mini'
llm_settings.OPENAI_API_KEY = 'xxxxx'


app = AgenticOrchestratorCore(
    base_settings=app_settings,
    llm_settings=llm_settings,
    llm_model=llm_settings.AGENT_MODEL,
    agent_tools=[]
)
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

uvicorn --reload --host 127.0.0.1 --port 8080 wsgi:app
```

</div>

### Step 6 - Index all your current subscriptions, processes, workflows and products:

!!! warning
    This will call out to external LLM services and cost money


<div class="termy">

```shell
python main.py index subscriptions
python main.py index products
python main.py index processes
python main.py index workflows  
```

</div>

### Step 7 - Profit :boom: :grin:

Visit the [ReDoc](http://127.0.0.1:8080/api/redoc) or [OpenAPI](http://127.0.0.1:8080/api/docs) to view and interact with the API.


### Next:

- [Create a product.](../workshops/advanced/domain-models.md)
- [Create a workflow for a product.](./workflows.md)
- [Generate products and workflows](../reference-docs/cli.md#generate)
