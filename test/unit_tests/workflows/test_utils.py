import warnings

import pytest

from orchestrator.workflow import StepList, Workflow, begin, done, step, workflow
from orchestrator.workflows.utils import (
    create_workflow,
    modify_workflow,
    reconcile_workflow,
    task,
    terminate_workflow,
    validate_workflow,
)


@step("Extra Step")
def extra_dummy_step():
    pass


def test_reconcile_workflow_basic():
    workflow_description = "Test Reconcile Workflow"

    @reconcile_workflow(workflow_description)  # type: ignore
    def test_workflow() -> StepList:
        return begin >> done

    workflow = test_workflow

    assert isinstance(workflow, Workflow)
    assert workflow.description == workflow_description
    assert workflow.target.name == "RECONCILE"
    step_names = [step.name for step in workflow.steps]

    expected_steps = [
        "Start",
        "Create Process Subscription relation",
        "Lock subscription",
        "Done",
        "Unlock subscription",
        "Refresh subscription search index",
        "Refresh process search index",
        "Done",
    ]
    assert step_names == expected_steps


def test_reconcile_workflow_additional_steps():
    workflow_description = "Test Reconcile Workflow with additional step"

    additional_step = StepList() >> extra_dummy_step

    @reconcile_workflow(workflow_description, additional_steps=additional_step)  # type: ignore
    def test_workflow() -> StepList:
        return begin >> done

    workflow = test_workflow

    assert isinstance(workflow, Workflow)
    assert workflow.description == workflow_description
    assert workflow.target.name == "RECONCILE"
    step_names = [step.name for step in workflow.steps]
    expected_steps = [
        "Start",
        "Create Process Subscription relation",
        "Lock subscription",
        "Done",
        "Extra Step",
        "Unlock subscription",
        "Refresh subscription search index",
        "Refresh process search index",
        "Done",
    ]
    assert step_names == expected_steps


def test_reconcile_workflow_empty_function_steps():
    workflow_description = "Test Reconcile Workflow empty steps"

    @reconcile_workflow(workflow_description)  # type: ignore
    def test_workflow() -> StepList:
        return StepList()

    workflow = test_workflow

    assert isinstance(workflow, Workflow)
    assert workflow.description == workflow_description
    assert workflow.target.name == "RECONCILE"

    step_names = [step.name for step in workflow.steps]
    expected_steps = [
        "Start",
        "Create Process Subscription relation",
        "Lock subscription",
        "Unlock subscription",
        "Refresh subscription search index",
        "Refresh process search index",
        "Done",
    ]
    assert step_names == expected_steps


def test_reconcile_workflow_decorated_function_raises():
    workflow_description = "Test Reconcile Workflow exception"

    def will_raise() -> StepList:
        raise RuntimeError("Something went wrong")

    with pytest.raises(RuntimeError, match="Something went wrong"):
        _ = reconcile_workflow(workflow_description)(will_raise)


def test_reconcile_workflow_non_callable():
    workflow_description = "Test Reconcile Workflow non-callable"

    with pytest.raises(TypeError):
        _ = reconcile_workflow(workflow_description)(None)


@pytest.mark.parametrize(
    "decorator_factory",
    [create_workflow, modify_workflow, terminate_workflow, validate_workflow, reconcile_workflow, workflow, task],
)
def test_deprecated_description_emits_warning(decorator_factory):
    description = "Deprecated description"

    with pytest.warns(DeprecationWarning):

        @decorator_factory(description)  # type: ignore[misc]
        def test_workflow() -> StepList:
            return begin >> done

    assert test_workflow.description == description


@pytest.mark.parametrize(
    "decorator_factory",
    [create_workflow, modify_workflow, terminate_workflow, validate_workflow, reconcile_workflow, workflow, task],
)
def test_empty_description_does_not_emit_warning(decorator_factory):
    with warnings.catch_warnings(record=True) as warnings_record:
        warnings.simplefilter("always")

        @decorator_factory("")  # type: ignore[misc]
        def test_workflow() -> StepList:
            return begin >> done

    description_warnings = [w for w in warnings_record if issubclass(w.category, DeprecationWarning)]
    assert description_warnings == []
    assert test_workflow.description == ""
