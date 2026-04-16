# Database

For most operation database interactions, you will want to use the CLI tool, which is documented in depth [here](cli.md#db). The rest of this page documents other unique things that you should know about the database in the WFO.

## Architecture

The WFO database is built on top of the [SQLAlchemy](https://www.sqlalchemy.org/) ORM, and we use [Alembic](https://alembic.sqlalchemy.org/en/latest/) for building database migrations. If you aren't familiar with these technologies, you should definitely read up on them to get a better understanding of how the orchestrator's database components work. The database models we use for the orchestrator-core live in `orchestrator-core/db/models.py`.

??? example "Example: `orchestrator-core/db/models.py`"
    ```python linenums="1"
    {% include '../../orchestrator/db/models.py' %}
    ```

## Setting Up the Database Initially

With a blank WFO instance, to setup the database properly, you simply need to run the `init` CLI command. More docs on how to use that command can be found [here.](cli.md#orchestrator.cli.database.init)

## Saving a Transaction in Your Workflow

Workflow step execution uses a per-step session-management model implemented in `orchestrator.workflow._run_step`. Each step runs under two nested `database_scope()` blocks — one for the work unit (pre-step reads, step body, model persistence) and a separate one for the logging unit (`_db_log_step` + process state update). This guarantees that a failed step is still persisted to `process_steps`, because the logging scope is fresh and opens regardless of whether the work scope raised.

Step authors don't normally need to do anything explicit: returning the step state at the end of the function is sufficient, and the framework handles the transaction boundaries. If you need to execute DB queries outside of a step (for example in a scheduled task, a Celery signal handler, or a CLI command), open a fresh scope with an explicit transaction:

```python
from orchestrator.db import db

with db.database_scope(), db.session.begin():
    ...
```

`WrappedSession` is an empty `sqlalchemy.orm.Session` subclass kept for type-hint compatibility; it no longer enforces any commit discipline because the framework now owns transaction boundaries via the per-step scope model.

::: orchestrator.db.database.WrappedSession
    options:
        heading_level: 3


## Multiple Heads

When you have multiple features in flight at a time with your WFO development process, you might come across this error when starting up your WFO instance, especially after performing `git` merges:

```python
Only a single head is supported. The script directory has multiple heads (due branching), which must be resolved by manually editing the revision files to form a linear sequence.
Run `alembic branches` to see the divergence(s).
```

Thankfully alembic is great at handling this and you can use the WFO CLI `db merge` command to resolve this, [documented in depth here.](cli.md#orchestrator.cli.database.merge)
