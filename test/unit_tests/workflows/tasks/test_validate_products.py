from types import SimpleNamespace
from unittest import mock

import pytest
from pydantic import ValidationError

import orchestrator.workflows.tasks.validate_products as validate_products
from orchestrator.db import WorkflowTable
from orchestrator.utils.errors import ProcessFailureError
from test.unit_tests.workflows import assert_complete, run_workflow


@pytest.mark.workflow
def test_check_subscriptions(generic_subscription_1, generic_subscription_2):
    result, process, step_log = run_workflow("task_validate_products", {})
    assert_complete(result)


@mock.patch("orchestrator.workflows.tasks.validate_products.get_workflow_by_name")
def test_check_workflows_validation_ignores_description_mismatch(mock_get_workflow_by_name):
    workflow_name = "dummy_workflow"

    class DummyLazyWorkflow:
        def instantiate(self):
            return type("Wf", (), {"name": workflow_name, "target": "CREATE", "description": "code desc"})()

    db_workflow = WorkflowTable(name=workflow_name, target="CREATE", description="db desc")

    with (
        mock.patch.object(
            validate_products.orchestrator.workflows, "ALL_WORKFLOWS", {workflow_name: DummyLazyWorkflow()}
        ),
        mock.patch.object(
            validate_products, "generate_translations", return_value={"workflow": {workflow_name: "Dummy Workflow"}}
        ),
    ):
        mock_get_workflow_by_name.return_value = db_workflow
        result = validate_products.check_workflows_for_matching_targets_and_descriptions({})

    assert result.issuccess()
    assert result.unwrap() == {"check_workflows_for_matching_targets_and_descriptions": True}


@mock.patch("orchestrator.workflows.tasks.validate_products.get_workflow_by_name")
def test_check_workflows_validation_fails_on_target_mismatch(mock_get_workflow_by_name):
    workflow_name = "dummy_workflow"

    class DummyLazyWorkflow:
        def instantiate(self):
            return type("Wf", (), {"name": workflow_name, "target": "CREATE", "description": "code desc"})()

    db_workflow = WorkflowTable(name=workflow_name, target="MODIFY")

    with mock.patch.object(
        validate_products.orchestrator.workflows, "ALL_WORKFLOWS", {workflow_name: DummyLazyWorkflow()}
    ):
        mock_get_workflow_by_name.return_value = db_workflow
        result = validate_products.check_workflows_for_matching_targets_and_descriptions({})

    assert result.isfailed()
    assert isinstance(result.unwrap(), ProcessFailureError)
    assert "none matching targets and names" in str(result.unwrap())


@mock.patch("orchestrator.workflows.tasks.validate_products.get_workflow_by_name")
def test_check_workflows_validation_fails_on_missing_translation(mock_get_workflow_by_name):
    workflow_name = "dummy_workflow"

    class DummyLazyWorkflow:
        def instantiate(self):
            return type("Wf", (), {"name": workflow_name, "target": "CREATE", "description": "code desc"})()

    with (
        mock.patch.object(
            validate_products.orchestrator.workflows, "ALL_WORKFLOWS", {workflow_name: DummyLazyWorkflow()}
        ),
        mock.patch.object(validate_products, "generate_translations", return_value={"workflow": {}}),
    ):
        mock_get_workflow_by_name.return_value = WorkflowTable(name=workflow_name, target="CREATE")
        result = validate_products.check_workflows_for_matching_targets_and_descriptions({})

    assert result.isfailed()
    assert isinstance(result.unwrap(), ProcessFailureError)
    assert "missing translations" in str(result.unwrap())


def test_check_all_workflows_are_in_db_fails_on_mismatch():
    with (
        mock.patch.object(validate_products.orchestrator.workflows, "ALL_WORKFLOWS", {"wf_code": object()}),
        mock.patch.object(validate_products, "get_workflows", return_value=[SimpleNamespace(name="wf_db")]),
    ):
        result = validate_products.check_all_workflows_are_in_db({})

    assert result.isfailed()
    assert isinstance(result.unwrap(), ProcessFailureError)
    assert "missing workflows" in str(result.unwrap())


@mock.patch("orchestrator.workflows.tasks.validate_products.db")
def test_check_subscription_models_validation_error(mock_db):
    sub = SimpleNamespace(subscription_id="sub-1")
    mock_db.session.scalars.return_value = [sub]

    with mock.patch.object(
        validate_products.SubscriptionModel,
        "from_subscription",
        side_effect=ValidationError.from_exception_data(title="test", line_errors=[], input_type="python"),
    ):
        result = validate_products.check_subscription_models({})

    assert result.isfailed()
    assert isinstance(result.unwrap(), ProcessFailureError)


@mock.patch("orchestrator.workflows.tasks.validate_products.db")
def test_check_subscription_models_generic_exception(mock_db):
    sub = SimpleNamespace(subscription_id="sub-2")
    mock_db.session.scalars.return_value = [sub]

    with mock.patch.object(
        validate_products.SubscriptionModel,
        "from_subscription",
        side_effect=RuntimeError("unexpected error"),
    ):
        result = validate_products.check_subscription_models({})

    assert result.isfailed()
    err = result.unwrap()
    assert isinstance(err, ProcessFailureError)
    assert "unexpected error" in str(err)


@mock.patch("orchestrator.workflows.tasks.validate_products.db")
def test_check_that_active_products_have_a_modify_note_failure(mock_db):
    """Products without modify_note raise ProcessFailureError."""
    mock_db.session.scalars.side_effect = [
        # First call: WorkflowTable.select().filter(...).first() via scalars
        mock.MagicMock(first=mock.MagicMock(return_value=SimpleNamespace(name="modify_note"))),
        # Second call: select(ProductTable).filter(...)
        [SimpleNamespace(name="ProductWithoutNote", workflows=[])],
    ]

    result = validate_products.check_that_active_products_have_a_modify_note({})

    assert result.isfailed()
    assert isinstance(result.unwrap(), ProcessFailureError)


@mock.patch("orchestrator.workflows.tasks.validate_products.db")
def test_check_subscription_models_success(mock_db):
    """All subscriptions load successfully."""
    sub = SimpleNamespace(subscription_id="sub-ok")
    mock_db.session.scalars.return_value = [sub]

    with mock.patch.object(
        validate_products.SubscriptionModel,
        "from_subscription",
        return_value=mock.MagicMock(),
    ):
        result = validate_products.check_subscription_models({})

    assert result.issuccess()
    assert result.unwrap()["check_subscription_models"] is True
