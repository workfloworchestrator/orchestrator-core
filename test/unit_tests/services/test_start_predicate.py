from http import HTTPStatus
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from orchestrator.db import ProcessTable, db
from orchestrator.services.processes import create_process, start_process
from orchestrator.targets import Target
from orchestrator.utils.errors import StartPredicateError
from orchestrator.workflow import PredicateContext, StepList, done, init, make_workflow, step, workflow
from test.unit_tests.workflows import WorkflowInstanceForTests, store_workflow


@step("Test step")
def test_step_fn():
    return {"result": True}


def always_true(context: PredicateContext) -> bool:
    return True


def always_false(context: PredicateContext) -> bool:
    return False


@pytest.fixture
def workflow_no_predicate():
    wf = workflow(
        "Test workflow without predicate",
        target=Target.SYSTEM,
    )(lambda: init >> test_step_fn >> done)
    with WorkflowInstanceForTests(wf, "test_wf_no_predicate") as wf_table:
        yield wf_table


@pytest.fixture
def workflow_true_predicate():
    wf = workflow(
        "Test workflow with passing predicate",
        target=Target.SYSTEM,
        run_predicate=always_true,
    )(lambda: init >> test_step_fn >> done)
    with WorkflowInstanceForTests(wf, "test_wf_true_predicate") as wf_table:
        yield wf_table


@pytest.fixture
def workflow_false_predicate():
    wf = workflow(
        "Test workflow with failing predicate",
        target=Target.SYSTEM,
        run_predicate=always_false,
    )(lambda: init >> test_step_fn >> done)
    with WorkflowInstanceForTests(wf, "test_wf_false_predicate") as wf_table:
        yield wf_table


def test_workflow_without_predicate_starts_normally(workflow_no_predicate):
    process_id = start_process("test_wf_no_predicate", user_inputs=[{}])
    process = db.session.get(ProcessTable, process_id)
    assert process is not None


def test_workflow_with_true_predicate_starts_normally(workflow_true_predicate):
    process_id = start_process("test_wf_true_predicate", user_inputs=[{}])
    process = db.session.get(ProcessTable, process_id)
    assert process is not None


def test_workflow_with_false_predicate_raises_error(workflow_false_predicate):
    with pytest.raises(StartPredicateError, match="test_wf_false_predicate"):
        start_process("test_wf_false_predicate", user_inputs=[{}])


def test_false_predicate_does_not_create_db_row(workflow_false_predicate):
    initial_count = db.session.scalar(
        select(ProcessTable).filter(ProcessTable.workflow_id == workflow_false_predicate.workflow_id)
    )

    with pytest.raises(StartPredicateError):
        create_process("test_wf_false_predicate", user_inputs=[{}])

    final_count = db.session.scalar(
        select(ProcessTable).filter(ProcessTable.workflow_id == workflow_false_predicate.workflow_id)
    )
    assert initial_count == final_count


def test_predicate_receives_correct_context(workflow_no_predicate):
    captured_context = {}

    def capturing_predicate(context: PredicateContext) -> bool:
        captured_context["workflow"] = context.workflow
        captured_context["workflow_key"] = context.workflow_key
        return True

    wf = workflow(
        "Test workflow with capturing predicate",
        target=Target.SYSTEM,
        run_predicate=capturing_predicate,
    )(lambda: init >> test_step_fn >> done)

    with WorkflowInstanceForTests(wf, "test_wf_capturing") as wf_table:
        start_process("test_wf_capturing", user_inputs=[{}])

    assert captured_context["workflow_key"] == "test_wf_capturing"
    assert captured_context["workflow"].name == "test_wf_capturing"
    assert captured_context["workflow"].description == "Test workflow with capturing predicate"
