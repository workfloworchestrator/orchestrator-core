# Copyright 2019-2026 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for workflow decorator utilities: reconcile_workflow step composition, deprecation warnings, obsolete_step, and ensure_provisioning_status."""

import warnings

import pytest

from orchestrator.core.workflow import StepList, Workflow, begin, done, step, workflow
from orchestrator.core.workflows.utils import (
    create_workflow,
    ensure_provisioning_status,
    modify_workflow,
    obsolete_step,
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

        @decorator_factory(description)  # type: ignore[untyped-decorator]
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

        @decorator_factory("")  # type: ignore[untyped-decorator]
        def test_workflow() -> StepList:
            return begin >> done

    description_warnings = [w for w in warnings_record if issubclass(w.category, DeprecationWarning)]
    assert description_warnings == []
    assert test_workflow.description == ""


def test_obsolete_step():
    result = obsolete_step({})
    assert result.issuccess()


def test_ensure_provisioning_status():
    @step("Dummy modify step")
    def dummy_modify():
        pass

    steplist = ensure_provisioning_status(dummy_modify)
    step_names = [s.name for s in steplist]
    assert step_names == ["Set subscription to 'provisioning'", "Dummy modify step", "Set subscription to 'active'"]


def test_task_with_initial_input_form():
    def my_input_form(state):
        return state

    my_task = task(initial_input_form=my_input_form)(lambda: begin >> done)

    assert isinstance(my_task, Workflow)
    assert my_task.initial_input_form is not None
