---
# tutorial | how-to | reference | explanation | mixed
diataxis:
reviewed: false
---

# Base application
<!-- diataxis: -->

The orchestrator-core is a standalone API with a workflow engine and database, similar to frameworks
like FastAPI, Flask and Django. You install the core library, initialise it with configuration and
run.

!!! note
    The Orchestrator-core is designed to be installed and extended just like a FastAPI or Flask application. For more
    information about how this works read the [Reference documentation](../reference-docs/app/app.md).

## Quick start with the cookiecutter
<!-- diataxis: -->

The fastest way to start a new orchestrator is with the
[orchestrator-cookiecutter](https://github.com/workfloworchestrator/orchestrator-cookiecutter).
It generates a complete project: source layout, database migrations, Celery worker (optional),
docker-compose (optional), test infrastructure and pre-commit hooks— all with one command.

### Prerequisites
<!-- diataxis: -->

- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- A PostgreSQL database (>= 15 with [pgvector](https://github.com/pgvector/pgvector))
- Docker (optional, for running Postgres and Redis locally)

### Step 1 - Generate the project
<!-- diataxis: -->

<div class="termy">

```shell
$ uvx orchestrator-cookiecutter
# [1/8] project_name (My Orchestrator): $ My Orchestrator
# [2/8] project_slug (my_orchestrator): $ my_orchestrator
# [3/8] package_name (my-orchestrator): $ my-orchestrator
# [4/8] description: $ A Workflow Orchestrator implementation for My Orchestrator.
# [5/8] author (ACME inc.): $ ACME inc.
# [6/8] author_email (devnull@example.com): $ devnull@example.com
# [7/8] executor [1-Threadpool, 2-Celery] (1): $ 2
# [8/8] Generate docker-compose.yml? [1-yes, 2-no] (1): $ 1
// Installing dependencies, git repo, pre-commit hooks, DB migrations...
---> 100%
 ==========  Completed cookiecutter install  ===========
```

</div>

The wizard asks for a project name, executor type (Threadpool or Celery) and whether to generate a
`docker-compose.yml`. It then installs dependencies, initialises a git repository with pre-commit
hooks, and creates the Alembic migration environment.

!!! tip
    Choose **Threadpool** to get started quickly. You can switch to **Celery** later by adding
    a `celery_worker.py` and setting `EXECUTOR=celery`; see
    [Scaling the Orchestrator](../guides/scaling.md).

### Step 2 - Start the database
<!-- diataxis: -->

If you chose to generate a `docker-compose.yml`:

<div class="termy">

```shell
cd my-orchestrator
docker compose up -d
```

</div>

Otherwise, point the app at your own PostgreSQL database:

```shell
export DATABASE_URI=postgresql+psycopg://<user>:<password>@<host>:<port>/<database>
```

The server needs pgvector; see [Postgres with pgvector](deployment.md#postgres-with-pgvector).

### Step 3 - Create the database schema
<!-- diataxis: -->

The migration environment (`migrations/`, `alembic.ini`) was already generated for you, so there is
no need to run `db init`. `main.py` lives in the package directory (e.g. `my_orchestrator/`):

<div class="termy">

```shell
uv run main.py db upgrade heads
```

</div>

### Step 4 - Run the app
<!-- diataxis: -->

<div class="termy">

```shell
uv run uvicorn --reload --host 127.0.0.1 --port 8080 wsgi:app
```

</div>

Visit the [OpenAPI docs](http://127.0.0.1:8080/api/docs) or
[ReDoc](http://127.0.0.1:8080/api/redoc) to interact with the API.

### Step 5 - Run the tests
<!-- diataxis: -->

<div class="termy">

```shell
uv run pytest
```

</div>

### What the cookiecutter generates
<!-- diataxis: -->

```
my-orchestrator/
├── my_orchestrator/
│   ├── __init__.py          # init_app() and init_cli_app()
│   ├── main.py              # CLI entrypoint
│   ├── wsgi.py              # ASGI entrypoint (uvicorn)
│   ├── celery_worker.py     # Celery worker (when chosen)
│   ├── products/            # Product types and blocks
│   ├── workflows/           # Workflow registrations
│   ├── services/            # Business logic
│   ├── utils/
│   ├── translations/        # UI translation strings
│   └── migrations/          # Alembic migration environment
├── test/                    # Test infrastructure with transactional rollback
├── pyproject.toml
├── docker-compose.yml       # Postgres + Redis (when chosen)
├── .pre-commit-config.yaml
└── README.md
```

### Next
<!-- diataxis: -->

- [Create a workflow for a product.](./workflows.md)
- [Generate products and workflows](../reference-docs/cli.md#generate)
- [Run your orchestrator in containers or on Kubernetes](./deployment.md)

---

## Manual setup
<!-- diataxis: -->

??? note "Setting up a project without the cookiecutter"

    If you prefer to set up a project manually, or need to understand what the cookiecutter does
    under the hood, follow these steps. The cookiecutter generates equivalent code for all of them.

    ### Step 1 - Install the package

    Create a virtualenv and install the core.

    === "uv"

        ```shell
        uv init my-orchestrator
        cd my-orchestrator
        uv add orchestrator-core
        ```

    === "pip"

        ```shell
        python -m venv .venv
        source .venv/bin/activate
        pip install orchestrator-core
        ```

### Step 2 - Setup the database
<!-- diataxis: -->

Create a postgres database:

<div class="termy">

```shell
createuser -sP nwa
createdb orchestrator-core -O nwa
```

</div>

Choose a password and remember it for later steps. The server needs pgvector; see
[Postgres with pgvector](deployment.md#postgres-with-pgvector).

As an example, you can run these docker commands in separate shells to start a temporary
postgres instance:

```shell
docker run --rm --name temp-orch-db -e POSTGRES_PASSWORD=rootpassword -p 5432:5432 pgvector/pgvector:pg17

docker exec -it temp-orch-db su - postgres -c 'createuser -sP nwa && createdb orchestrator-core -O nwa'
```

### Step 3 - Create the main.py and wsgi.py
<!-- diataxis: -->

Create a `main.py` file.
This provides the CLI entrypoint to your Orchestrator.

=== "`orchestrator-core` >= 5.0"

    ```python
    import typer
    from nwastdlib.logging import initialise_logging
    from orchestrator.core import app_settings
    from orchestrator.core.cli.main import app as core_cli
    from orchestrator.core.db import init_database
    from orchestrator.core.log_config import LOGGER_OVERRIDES

    def init_cli_app() -> typer.Typer:
        initialise_logging(LOGGER_OVERRIDES)
        init_database(app_settings)
        return core_cli()

    if __name__ == "__main__":
        init_cli_app()
    ```

=== "`orchestrator-core` < 5.0"

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

=== "`orchestrator-core` >= 5.0"

    ```python
    from orchestrator.core import OrchestratorCore
    from orchestrator.core.settings import app_settings

    app = OrchestratorCore(base_settings=app_settings)
    app.register_graphql()
    ```

=== "`orchestrator-core` < 5.0"

    ```python
    from orchestrator import OrchestratorCore
    from orchestrator.settings import app_settings

    app = OrchestratorCore(base_settings=app_settings)
    app.register_graphql()
    ```

### Step 4 - Run the database migrations
<!-- diataxis: -->

Initialize the migration environment and database tables.

<div class="termy">

```shell
export DATABASE_URI=postgresql+psycopg://nwa:PASSWORD_FROM_STEP_2@localhost:5432/orchestrator-core

python main.py db init
python main.py db upgrade heads
```

</div>

### Step 5 - Run the app
<!-- diataxis: -->

<div class="termy">

```shell
export DATABASE_URI=postgresql+psycopg://nwa:PASSWORD_FROM_STEP_2@localhost:5432/orchestrator-core
export OAUTH2_ACTIVE=False

uvicorn --reload --host 127.0.0.1 --port 8080 wsgi:app
```

</div>

### Step 6 - Verify
<!-- diataxis: -->

Visit the [ReDoc](http://127.0.0.1:8080/api/redoc) or
[OpenAPI](http://127.0.0.1:8080/api/docs) to view and interact with the API.

### Next

- [Prepare the source folder.](./prepare-source-folder.md)
- [Create a workflow for a product.](./workflows.md)
- [Generate products and workflows](../reference-docs/cli.md#generate)
- [Run your orchestrator in containers or on Kubernetes](./deployment.md)
