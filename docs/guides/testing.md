# Writing unit tests

This guide covers how to write unit tests for workflows and domain models using orchestrator-core.
For setup instructions (database, running tests), see [development.md](../contributing/development.md).

## Test helpers

Workflow tests use a set of helpers from `test.unit_tests.workflows`:

```python
from test.unit_tests.workflows import (
    WorkflowInstanceForTests,
    assert_aborted,
    assert_assignee,
    assert_awaiting_callback,
    assert_complete,
    assert_failed,
    assert_product_blocks_equal,
    assert_state,
    assert_state_equal,
    assert_step_name,
    assert_success,
    assert_suspended,
    assert_waiting,
    extract_error,
    extract_state,
    resume_workflow,
    run_workflow,
    run_form_generator,
)
```

`run_workflow(workflow_key, input_data)` starts a workflow and returns `(result, process, step_log)`.
`resume_workflow(process, step_log, input_data)` resumes a suspended workflow and returns `(result, step_log)`.

The `assert_*` helpers for terminal state each raise with a descriptive message on failure:

- `assert_complete(result)` — asserts the workflow completed successfully.
- `assert_success(result)` — asserts the result is a success (use when you want to check `issuccess()` rather than `iscomplete()`).
- `assert_failed(result)` — asserts the workflow failed.
- `assert_suspended(result)` — asserts the workflow is suspended at an input step.
- `assert_waiting(result)` — asserts the workflow is in a waiting state.
- `assert_awaiting_callback(result)` — asserts the workflow is waiting for a callback.
- `assert_aborted(result)` — asserts the workflow was aborted.

`assert_state(result, expected)` checks that the result state contains at least the keys in `expected`.
`assert_state_equal(result, expected, excluded_keys=None)` checks the full state for equality, minus a set of excluded keys (defaults to `process_id`, `workflow_target`, `workflow_name`).

`assert_assignee(log, expected)` and `assert_step_name(log, expected)` inspect the last entry of the step log — useful for verifying which step a workflow stopped on and who it was assigned to.

`assert_product_blocks_equal(expected, actual)` compares lists of product block instance dicts, sorting by block type before comparison.

`extract_state(result)` unwraps the state dict from a result; `extract_error(result)` pulls the error string from a failed result.

## Writing a workflow test

### Simple workflow (no suspension)

Mark workflow tests with `@pytest.mark.workflow`. The `responses` HTTP mock fixture is active automatically (see [HTTP mocking](#http-mocking)); include it in the test signature only when you need to register mocks with `responses.add()`:

```python
import pytest
from orchestrator.db import ProductTable
from sqlalchemy import select
from test.unit_tests.workflows import assert_complete, extract_state, run_workflow

@pytest.mark.workflow
def test_create_my_product(responses, db_session):
    product = db_session.scalars(select(ProductTable).where(ProductTable.name == "MyProduct")).one()

    result, process, step_log = run_workflow(
        "create_my_product",
        [{"product": product.product_id}, {"customer_id": CUSTOMER_ID, "field": "value"}],
    )

    assert_complete(result)
    state = extract_state(result)
    assert state["field"] == "value"
```

The `input_data` argument is a list of dicts — one dict per form page in the workflow. Create workflows typically take `[{"product": product_id}, {...field inputs...}]`.

### Multi-step workflow (with suspension)

When a workflow suspends at an `inputstep`, assert the suspension, inspect state, then resume with the next form's data:

```python
@pytest.mark.workflow
def test_create_with_approval(responses, db_session):
    product = db_session.scalars(select(ProductTable).where(ProductTable.name == "MyProduct")).one()

    result, process, step_log = run_workflow(
        "create_my_product",
        [{"product": product.product_id}, {"customer_id": CUSTOMER_ID}],
    )
    assert_suspended(result)

    state = extract_state(result)
    assert state["customer_id"] == CUSTOMER_ID

    result, step_log = resume_workflow(process, step_log, {"approved": True})
    assert_complete(result)
```

Pass only the new form's data to `resume_workflow` — it merges into the existing state automatically.
Repeat the `assert_suspended` / `resume_workflow` cycle for each suspension point.

### Testing an ad-hoc workflow

To test a workflow defined inline (not registered in `ALL_WORKFLOWS`), use `WorkflowInstanceForTests` as a context manager:

```python
from orchestrator.targets import Target
from orchestrator.workflow import begin, done, inputstep, step, workflow
from test.unit_tests.workflows import WorkflowInstanceForTests, assert_complete, assert_suspended, resume_workflow, run_workflow

def test_my_inline_workflow():
    @step("Do work")
    def do_work():
        return {"result": 42}

    @workflow(target=Target.CREATE)
    def my_wf():
        return begin >> do_work >> done

    with WorkflowInstanceForTests(my_wf, "my_wf"):
        result, process, step_log = run_workflow("my_wf", {})
        assert_complete(result)
```

## HTTP mocking

The `responses` fixture is `autouse=True`, meaning it is active for every test automatically.
Any HTTP call that is not mocked will raise an exception and fail the test.
Any mock that is registered but never called will also fail the test — register only what your workflow actually uses.

Register mocks before running the workflow:

```python
@pytest.mark.workflow
def test_with_external_call(responses, db_session):
    responses.add(
        "POST",
        "https://external.example.com/api/endpoint",
        body='{"status": "ok"}',
        content_type="application/json",
    )

    result, process, step_log = run_workflow("my_workflow", [...])
    assert_complete(result)
```

If your URL includes a query string, pass `match_querystring=True` to `responses.add()` or the mock will not match:

```python
responses.add(
    "GET",
    "https://api.example.com/items?id=123",
    body='{"id": 123}',
    content_type="application/json",
    match_querystring=True,
)
```

Skipping the `match_querystring` flag on a query-string URL is a common source of mocks silently not matching.

To opt a specific test out of the responses mock entirely, mark it with `@pytest.mark.noresponses`.

## Writing subscription fixtures

When creating a subscription fixture in `conftest.py` for use in workflow tests, always set `insync=True`:

```python
gen_subscription = MyProductInactive.from_product_id(
    product_id, customer_id=CUSTOMER_ID, insync=True
)
```

Omitting `insync=True` will cause any workflow test consuming that subscription to fail with a message about an active process — the framework thinks the subscription is mid-process and refuses to proceed.

## Writing domain model tests

Domain model tests exercise product types and product blocks directly, without running a workflow.

### Testing default field values

```python
from products.product_types.my_product import MyProductInactive

def test_my_product_defaults():
    subscription = MyProductInactive.from_product_id(product_id, customer_id=CUSTOMER_ID)
    assert subscription.pb.some_field == "expected_default"
```

### Testing save and load

Define a fixture in `conftest.py` that creates and persists the subscription, then load it from the database in the test:

```python
def test_my_product_save_and_load(my_product_subscription_id):
    subscription = MyProduct.from_subscription(my_product_subscription_id)
    assert subscription.status == SubscriptionLifecycle.ACTIVE

    subscription.pb.some_field = "updated"
    subscription.save()

    reloaded = MyProduct.from_subscription(my_product_subscription_id)
    assert reloaded.pb.some_field == "updated"
```

## Testing form generators

Use `run_form_generator` to test multi-page form logic in isolation, without running a full workflow:

```python
from test.unit_tests.workflows import run_form_generator

def test_my_form_generator():
    forms, result = run_form_generator(
        my_form_generator({"state_field": "value"}),
        extra_inputs=[{"page_1_field": "input"}],
    )
    assert result["page_1_field"] == "input"
    assert result["computed_field"] == "expected"
```

Note that `run_form_generator` intentionally bypasses Pydantic validation — ensure `extra_inputs` matches the expected types as if validation had run.

## Test markers

| Marker | When to use |
|--------|-------------|
| `@pytest.mark.workflow` | All workflow tests — required for correct test collection and fixtures |
| `@pytest.mark.noresponses` | Tests that make real HTTP calls (rare; use with caution) |
| `@pytest.mark.celery` | Tests requiring Celery worker support |
| `@pytest.mark.search` | Tests requiring the `search` extra |
| `@pytest.mark.acceptance` | Acceptance tests (handled separately from unit tests) |
