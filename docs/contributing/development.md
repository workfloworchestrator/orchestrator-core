# Setting up a development environment

To add features to the repository follow the following procedure to setup a working development environment.

## Installation

Install the project and its dependencies to develop on the code.

### Step 1 - install uv

Follow the [installing uv](https://docs.astral.sh/uv/getting-started/installation/) instructions.

### Step 2 - install project and dependencies

```
uv sync --all-groups --all-extras
```

This creates a virtual environment at `.venv` with the latest dependencies and version of python.
You can activate it, but recommended practice is to prefix python commands with `uv run <command>` as we'll show below.

More details in [About UV](#about-uv).

## Running tests

Run the unit-test suite to verify a correct setup.

### Step 1 - Create a database

Setup a postgres database (see [Getting Started](../getting-started/base.md#step-2---setup-the-database)).

Create a database and user:

``` shell
createuser -sP nwa
createdb orchestrator-core-test -O nwa
```

Set the password to something simple, like `nwa`.

### Step 2 - Run tests

Ensure the application can reach the database:
```
export DATABASE_URI=postgresql://nwa:nwa@localhost:5432/orchestrator-core-test
```

``` shell
uv run pytest test/unit_tests
```

If you do not encounter any failures in the test, you should be able to develop features in the orchestrator-core.


## Adding to the documentation

Documentation for the Orchestrator is written by using [Mkdocs](https://www.mkdocs.org/).
To contribute to them follow the instructions above to `step 2`, you can then develop them locally by running:

```bash
uv run mkdocs serve
```

This should make the docs available on your local machine here: [http://127.0.0.1:8000/orchestrator-core/](http://127.0.0.1:8000/orchestrator-core/)

## About UV

uv is a very fast replacement for pip and flit which also adds a lot of functionality.
This section explains a few concepts relevant to know when developing on the orchestrator-core.
For a full overview consult the [uv documentation](https://docs.astral.sh/uv/).

### Update dependencies

To ensure your local environment (and the lockfile) contain the latest version of each dependency, add `--upgrade` to the sync command.

For example:
```
uv sync --all-groups --all-extras --upgrade
```

### Adding and removing dependencies

Instead of manually editing `pyproject.toml` you can use `uv add`.

For example, let's say we want to become an enterprise application :-)

```
uv add django  # adds "django>=5.2.3" to pyproject.toml
```

Apart from updating `pyproject.toml` uv also installs the dependency (and subdependencies) in your environment.

It is a uv default to specify the lower limit.
You can also let uv set an upper limit or set it explicitly:

```
uv add django --bounds minor   # "django>=5.2.3,<5.3.0"
uv add django --bounds major   # "django>=5.2.3,<6.0.0"
uv add 'django>=5.2.3,<6.0.0'  # "django>=5.2.3,<6.0.0"
```

To remove the dependency you can run:

```
uv remove django
```

**Note**: The add/remove commands can be given the options, `--group <groupname>` or `--optional <optionalname>` to target a specific group or optional.


### Python interpreter

uv will create the venv with the latest python version supported by orchestrator-core.
If that version is not found on your machine, it is automatically downloaded.
Check the output of `uv help python` how to change this behavior.

### uv sync

The `uv sync` syncs your environment (`.venv`) based on the options you give it and what's configured in `pyproject.toml`.

A few examples of different options:

```
# base dependencies
uv sync --no-dev

# base + development dependencies
uv sync

# base + development + celery dependencies
uv sync --extra celery

# base + development + mkdocs dependencies
uv sync --group docs
```

uv removes anything not specified in the command or `pyproject.toml` to ensure a clean and reproducible environment.

### What is uv.lock for?

The lockfile is used for development and testing of the orchestrator-core.
It captures the exact set of dependencies used to create the local environment.

Anytime you execute `uv run` or `uv sync` the lockfile is updated if necessary.
These updates must be committed because the CI pipeline will fail otherwise.
It can also be updated explicitly with `uv lock`.

When installing orchestrator-core in another project the lockfile is no longer relevant.
In that case only the broad requirements from `pyproject.toml` apply.

More information on the [uv website](https://docs.astral.sh/uv/concepts/projects/layout/#the-lockfile).

## Useful settings

### SQLAlchemy logging

WFO uses [SQLAlchemy](https://www.sqlalchemy.org/) for its ORM and DB connection management capabilities.

To get information about which DB queries it is performing, adjust it's loglevel through this environment variable:

```bash
LOG_LEVEL_SQLALCHEMY_ENGINE=INFO
```

Set it to `DEBUG` for even more information.

**Both INFO and DEBUG generate a *lot* of logging! It is not recommended to use this in production.**

### GraphQL query statistics

To get basic statistics per executed GraphQL Query, set the following environment variable:

```bash
ENABLE_GRAPHQL_STATS_EXTENSION=true
```

This will add the following details to the result of the query, as well as logging them.

```json
{
    "data": [],
    "extensions": {
        "stats": {
            "db_queries": 7,
            "db_time": 0.006837368011474609,
            "operation_time": 0.11549711227416992
        }
    }
}
```

The following should be noted:
* this requires monitoring of executed SQLAlchemy cursor events, which may have *some* overhead
* the number of queries can most likely be skewed by async FastAPI REST calls that take place, so it's recommended to use this in an isolated and controlled environment


### GraphQL query profiling

It is possible to profile GraphQL queries by enabling the [PyInstrument](https://github.com/joerick/pyinstrument) extension:

```bash
ENABLE_GRAPHQL_PROFILING_EXTENSION=true
```

This will create a file `pyinstrument.html` in the repository root which shows which parts of the code are taking up most of the execution time.

Note that you need to have the orchestrator-core's test dependencies installed.

**This has a lot of overhead and we advise you to not use this in production.**
