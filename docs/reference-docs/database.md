---
# tutorial | how-to | reference | explanation | mixed
diataxis:
reviewed: false
---

# Database
<!-- diataxis: -->

For most operation database interactions, you will want to use the CLI tool, which is documented in depth [here](cli.md#db). The rest of this page documents other unique things that you should know about the database in the WFO.

## Architecture
<!-- diataxis: -->

The WFO database is built on top of the [SQLAlchemy](https://www.sqlalchemy.org/) ORM, and we use
[Alembic](https://alembic.sqlalchemy.org/en/latest/) for building database migrations. If you aren't familiar with
these technologies, you should definitely read up on them to get a better understanding of how the orchestrator's
database components work. The database models we use for the orchestrator-core live in `orchestrator-core/db/models.py`.

??? example "Example: `orchestrator-core/db/models.py`"
    ```python linenums="1"
    {% include '../../orchestrator/core/db/models.py' %}
    ```

## Setting Up the Database Initially
<!-- diataxis: -->

With a blank WFO instance, to setup the database properly, you simply need to run the `init` CLI command. More docs on
how to use that command can be found [here.](cli.md#orchestrator.core.cli.database.init)

## Saving a Transaction in Your Workflow
<!-- diataxis: -->

An important thing to understand about interacting with the database inside of workflow steps is that saving to the
database in disabled during the workflow step. When a subscription is returned at the end of a step, then all of the
appropriate saving in the database occurs. You can see how we do this with the `WrappedSession` class we made around
the SQLAlchemy `Session` object:

::: orchestrator.core.db.database.WrappedSession
    options:
        heading_level: 3

## Connection pool
<!-- diataxis: reference -->

Each process has two engines, each with its own pool: a synchronous one (used by synchronous endpoints, workflows and
Celery tasks, via `db.session`) and an asynchronous one (used by async endpoints and GraphQL, via
`db.async_session()`). The settings below apply to both pools alike.

| Setting | Default | Meaning |
|---|---|---|
| `DATABASE_POOL_SIZE` | `60` | Persistent connections per pool. |
| `DATABASE_MAX_OVERFLOW` | `10` | Extra connections above the pool size, closed when returned. `0` caps the pool. |
| `DATABASE_POOL_TIMEOUT` | `30` | Seconds to wait for a connection before giving up. `0` fails fast. |

```shell
export DATABASE_POOL_SIZE=10
export DATABASE_MAX_OVERFLOW=5
export DATABASE_POOL_TIMEOUT=10
```

Sizes are per pool, so per process. With the defaults, each process can open up to `2 × (60 + 10) = 140` connections.
Up to 120 of these remain open when idle. The 20 overflow connections close when returned. Add up all API, scheduler
and Celery worker processes and stay well below Postgres' `max_connections` (default 100). The defaults suit a single
instance. With multiple processes, use a smaller pool per process, such as `10` persistent and `5` overflow connections.

For backwards compatibility, a pool key patched into `ENGINE_ARGUMENTS` to a value other than its built-in default
overrides its setting. A patch equal to the default, such as `pool_size = 60`, is indistinguishable from the shipped
configuration, so the corresponding setting still applies.

## Pool exhaustion
<!-- diataxis: reference -->

A request that waits longer than `DATABASE_POOL_TIMEOUT` for a connection gets `503 Service Unavailable` with a
`Retry-After: 5` header:

```json
{"detail": "The database connection pool is exhausted. Please try again later.", "status": 503, "title": "Service Unavailable"}
```

GraphQL cannot answer with a status code, so it returns `200` with the field in `errors` (`error_type`
`internal_error`) and no data, so retry the query.

The log line says which timeout it was:

| Log message | Meaning |
|---|---|
| `Database connection pool exhausted` | SQLAlchemy reported that the pool limit (`DATABASE_POOL_SIZE` + `DATABASE_MAX_OVERFLOW`) was reached and no connection was returned in time. |
| `Timed out waiting for a database connection` | A timeout that SQLAlchemy did not report as a pool limit error. The cause is unknown. |

An exhausted pool says that all connections were in use, not why. The pool recovers on its own as connections are
returned, so occasional 503s during a load peak are expected. Persistent or frequent 503s have one of these causes:

| Cause | What happens | What to check |
|---|---|---|
| Pool too small for the load | More concurrent requests than `DATABASE_POOL_SIZE` + `DATABASE_MAX_OVERFLOW` of one pool. | Whether the 503s follow the request volume. Raise the pool size only after ruling out the causes below, and keep the total below Postgres' `max_connections` (see above). |
| Connections held too long | Slow queries or long-running transactions keep connections checked out, so the pool drains even under moderate load. | Long-running queries and transactions, for example in `pg_stat_activity`. |
| Database not responding | Queries hang, for example during a failover or a lock pile-up, so connections never come back and every new request times out. | Whether the database is reachable and responsive, independent of the orchestrator. |

A raised pool size does not help with the last two causes: it only postpones the timeouts, and adds load on a database
that is already struggling.

## Multiple Heads
<!-- diataxis: -->

When you have multiple features in flight at a time with your WFO development process, you might come across this error
when starting up your WFO instance, especially after performing `git` merges:

```
Only a single head is supported. The script directory has multiple heads (due branching), which must be resolved by
manually editing the revision files to form a linear sequence. Run `alembic branches` to see the divergence(s).
```

This means that two migrations share the same `down_revision`. You can resolve this with the WFO CLI `db merge`
command, [documented in depth here](cli.md#orchestrator.core.cli.database.merge), or by re-parenting one of the
migrations. See [Managing Diverging Database Migrations](../guides/database-migrations.md) for how the `schema` and
`data` branches are organised, when to use which approach, and how to prevent divergence.
