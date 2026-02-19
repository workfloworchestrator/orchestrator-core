# Run Predicates

Run predicates allow you to conditionally prevent a workflow from starting. A predicate is a callable attached to a workflow via its decorator. It is evaluated before the process is created in the database. If the predicate rejects the workflow, a `StartPredicateError` is raised and no database row is created.

## How it works

When `create_process()` is called (via the REST API, GraphQL, a scheduler, or `start_process()` directly), the following happens:

1. The workflow is looked up from the registry
2. If `run_predicate` is set on the workflow, it is called with a `PredicateContext`
3. The predicate returns a tuple `(allowed, reason)`
4. If `allowed` is `False`, a `StartPredicateError` is raised with the optional `reason`
5. If `allowed` is `True`, the process is created normally

The error is then handled by each caller:

| Caller | Behavior |
|--------|----------|
| REST API | Returns HTTP 412 Precondition Failed with the reason in the response body |
| GraphQL | Returns a `MutationError` with `message="Start predicate not satisfied"` and the reason in `details` |
| Scheduler | Logs an info message and skips the run |

## PredicateContext

Every predicate receives a `PredicateContext` as its first argument. This is a frozen dataclass with:

| Field | Type | Description |
|-------|------|-------------|
| `workflow` | `Workflow` | The full workflow object (name, description, target, steps, etc.) |
| `workflow_key` | `str` | The string key used to look up the workflow (e.g. `"task_validate_products"`) |

You can use the context or ignore it depending on your needs.

## Defining a predicate

A predicate is any callable that accepts a `PredicateContext` and returns `tuple[bool, str | None]`:

- `(True, None)` - allow the workflow to start
- `(False, "reason")` - block the workflow, with an explanation
- `(False, None)` - block the workflow, using a default message

### Simple function

```python
from orchestrator.workflow import PredicateContext, workflow

def is_maintenance_window(context: PredicateContext) -> tuple[bool, str | None]:
    from datetime import datetime
    now = datetime.now()
    if 2 <= now.hour <= 6:
        return True, None
    return False, f"Workflow '{context.workflow_key}' can only run during maintenance window (02:00-06:00)"

@workflow("Risky migration", run_predicate=is_maintenance_window)
def risky_migration():
    ...
```

### Lambda

```python
@workflow("Quick task", run_predicate=lambda ctx: (True, None))
def quick_task():
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
