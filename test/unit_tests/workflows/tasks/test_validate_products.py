import pytest

import orchestrator.workflows.tasks.validate_products as validate_products
from orchestrator.utils.errors import ProcessFailureError
from test.unit_tests.workflows import assert_complete, run_workflow


@pytest.mark.workflow
def test_check_subscriptions(generic_subscription_1, generic_subscription_2):
    result, process, step_log = run_workflow("task_validate_products", {})
    assert_complete(result)


def test_check_workflows_validation_ignores_description_mismatch(monkeypatch):
    workflow_name = "dummy_workflow"

    class DummyLazyWorkflow:
        def instantiate(self):
            return type("Wf", (), {"name": workflow_name, "target": "CREATE", "description": "code desc"})()

    db_workflow = type("DbWf", (), {"name": workflow_name, "target": "CREATE", "description": "db desc"})()

    monkeypatch.setattr(validate_products.orchestrator.workflows, "ALL_WORKFLOWS", {workflow_name: DummyLazyWorkflow()})
    monkeypatch.setattr(validate_products, "get_workflow_by_name", lambda _name: db_workflow)
    monkeypatch.setattr(validate_products, "generate_translations", lambda _lang: {"workflow": {workflow_name: "ok"}})

    result = validate_products.check_workflows_for_matching_targets_and_descriptions({})

    assert result.issuccess()
    assert result.unwrap() == {"check_workflows_for_matching_targets_and_descriptions": True}


def test_check_workflows_validation_fails_on_target_mismatch(monkeypatch):
    workflow_name = "dummy_workflow"

    class DummyLazyWorkflow:
        def instantiate(self):
            return type("Wf", (), {"name": workflow_name, "target": "CREATE"})()

    db_workflow = type("DbWf", (), {"name": workflow_name, "target": "MODIFY"})()

    monkeypatch.setattr(validate_products.orchestrator.workflows, "ALL_WORKFLOWS", {workflow_name: DummyLazyWorkflow()})
    monkeypatch.setattr(validate_products, "get_workflow_by_name", lambda _name: db_workflow)

    result = validate_products.check_workflows_for_matching_targets_and_descriptions({})

    assert result.isfailed()
    assert isinstance(result.unwrap(), ProcessFailureError)
    assert "none matching targets and names" in str(result.unwrap())
