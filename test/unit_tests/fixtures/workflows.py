import pytest

from orchestrator.config.assignee import Assignee
from orchestrator.db import WorkflowTable, db
from orchestrator.targets import Target
from orchestrator.utils.datetime import nowtz
from orchestrator.workflow import (
    done,
    init,
    inputstep,
    retrystep,
    step,
    workflow,
)
from pydantic_forms.core import FormPage


@step("Step 1")
def step1(test_field):
    return {"steps": [1], "has_test_field": test_field}


@step("Step 2")
def step2(steps):
    return {"steps": [*steps, 2]}


@step("Step 3")
def step3(steps):
    return {"steps": [*steps, 3]}


@inputstep("Input step", assignee=Assignee.SYSTEM)
def input_step():
    class TestForm(FormPage):
        test_field_2: str

    input = yield TestForm
    return input.model_dump()


@step("Input step")
def check_input_data_step(test_field_2):
    return {"has_test_field_2": test_field_2}


@retrystep("Waiting step")
def fail_retry_step():
    raise ValueError("Failure Message")


@step("Fail")
def fail_step():
    raise ValueError("Failure Message")


def initial_input_form():
    class TestForm(FormPage):
        test_field: str

    input = yield TestForm
    return input.model_dump()


@workflow("Sample workflow", initial_input_form=initial_input_form)
def _sample_workflow():
    return init >> step1 >> step2 >> step3 >> done


@pytest.fixture
def sample_workflow():
    return _sample_workflow


@workflow("Sample workflow with suspend", initial_input_form=initial_input_form)
def _sample_workflow_with_suspend():
    return init >> step1 >> input_step >> check_input_data_step >> done


@pytest.fixture
def sample_workflow_with_suspend():
    return _sample_workflow_with_suspend


@pytest.fixture
def add_soft_deleted_workflows():
    def _add_soft_deleted_workflow(n: int):
        for i in range(n):
            db.session.add(
                WorkflowTable(
                    name=f"deleted_workflow_{i}",
                    description="deleted workflow",
                    target=Target.SYSTEM,
                    deleted_at=nowtz(),
                )
            )
        db.session.commit()

    return _add_soft_deleted_workflow
