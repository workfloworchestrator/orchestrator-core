# Run Predicates

Run predicates allow you to conditionally prevent a workflow from starting. A predicate is a callable attached to a workflow via its decorator. It is evaluated before the process is created in the database. If the predicate rejects the workflow, a `StartPredicateError` is raised and no database row is created.

## How it works

When `create_process()` is called (via the REST API, GraphQL, a scheduler, or `start_process()` directly), the following happens:

1. The workflow is looked up from the registry
2. If `run_predicate` is set on the workflow, it is called
3. The predicate returns a tuple `(allowed, reason)`
4. If `allowed` is `False`, a `StartPredicateError` is raised with the optional `reason`
5. If `allowed` is `True`, the process is created normally

The error is then handled by each caller:

| Caller | Behavior |
|--------|----------|
| REST API | Returns HTTP 412 Precondition Failed with the reason in the response body |
| GraphQL | Returns a `MutationError` with `message="Start predicate not satisfied"` and the reason in `details` |
| Scheduler | Logs an info message and skips the run |

## Defining a predicate

A predicate is any callable that returns `tuple[bool, str | None]`:

- `(True, None)` - allow the workflow to start
- `(False, "reason")` - block the workflow, with an explanation
- `(False, None)` - block the workflow, using a default message

### Simple function

```python
from orchestrator.workflow import workflow

def is_maintenance_window() -> tuple[bool, str | None]:
    from datetime import datetime
    now = datetime.now()
    if 2 <= now.hour <= 6:
        return True, None
    return False, "Workflow can only run during maintenance window (02:00-06:00)"

@workflow("Risky migration", run_predicate=is_maintenance_window)
def risky_migration():
    ...
```

### Lambda

```python
@workflow("Quick task", run_predicate=lambda: (True, None))
def quick_task():
    ...
```

### Factory (for parameterized predicates)

When a predicate needs configuration, use a factory function that returns a callable:

```python
from orchestrator.workflows.predicates import no_uncompleted_instance

@workflow(
    "Validate products",
    run_predicate=no_uncompleted_instance("task_validate_products"),
)
def task_validate_products():
    ...
```

`no_uncompleted_instance` is a built-in factory that returns a predicate checking whether any uncompleted process exists for the given workflow name.

You can write your own factories:

```python
def max_concurrent(workflow_name: str, limit: int) -> Callable[[], tuple[bool, str | None]]:
    def predicate() -> tuple[bool, str | None]:
        running = db.session.scalar(
            select(func.count())
            .select_from(ProcessTable)
            .filter(
                ProcessTable.workflow.has(name=workflow_name),
                ProcessTable.last_status == "running",
            )
        )
        if running < limit:
            return True, None
        return False, f"Already {running} running instances (limit: {limit})"
    return predicate

@workflow("Heavy task", run_predicate=max_concurrent("heavy_task", 3))
def heavy_task():
    ...
```

## Supported decorators

`run_predicate` is available on all workflow decorators:

- `@workflow`
- `@create_workflow`
- `@modify_workflow`
- `@terminate_workflow`
- `@validate_workflow`
- `@reconcile_workflow`

## Default behavior

The default is `run_predicate=None`, which means no predicate is evaluated and the workflow starts unconditionally. Existing workflows are unaffected.

## Built-in predicates

::: orchestrator.workflows.predicates
    options:
        heading_level: 3

## Error handling

::: orchestrator.utils.errors.StartPredicateError
    options:
        heading_level: 3
