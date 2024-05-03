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

An important thing to understand about interacting with the database inside of workflow steps is that saving to the database in disabled during the workflow step. When a subsription is returned at the end of a step, then all of the appropriate saving in the database occurs. You can see how we do this with the `WrappedSession` class we made around the SQLAlchemy `Session` object:

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
