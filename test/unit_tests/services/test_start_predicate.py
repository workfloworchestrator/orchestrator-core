import pytest
from sqlalchemy import func, select

from orchestrator.db import ProcessTable, db
from orchestrator.services.processes import create_process
from orchestrator.targets import Target
from orchestrator.utils.errors import StartPredicateError
from orchestrator.workflow import begin, done, step, workflow
from test.unit_tests.workflows import WorkflowInstanceForTests, assert_complete, run_workflow


def test_workflow_without_predicate_starts_normally():
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow("Test workflow without predicate", target=Target.SYSTEM)
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_no_predicate"):
        result, process, step_log = run_workflow("test_wf_no_predicate", {})
        assert_complete(result)


def test_workflow_with_true_predicate_starts_normally():
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow("Test workflow with passing predicate", target=Target.SYSTEM, run_predicate=lambda: True)
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_true_predicate"):
        result, process, step_log = run_workflow("test_wf_true_predicate", {})
        assert_complete(result)


def test_workflow_with_false_predicate_raises_error():
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow("Test workflow with failing predicate", target=Target.SYSTEM, run_predicate=lambda: False)
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_false_predicate"):
        with pytest.raises(StartPredicateError, match="test_wf_false_predicate"):
            run_workflow("test_wf_false_predicate", {})


def test_false_predicate_does_not_create_db_row():
    @step("Test step")
    def test_step_fn():
        return {"result": True}

    @workflow("Test workflow no db row", target=Target.SYSTEM, run_predicate=lambda: False)
    def test_wf():
        return begin >> test_step_fn >> done

    with WorkflowInstanceForTests(test_wf, "test_wf_no_db_row") as wf_table:
        initial_count = db.session.scalar(
            select(func.count()).select_from(ProcessTable).filter(ProcessTable.workflow_id == wf_table.workflow_id)
        )

        with pytest.raises(StartPredicateError):
            create_process("test_wf_no_db_row", user_inputs=[{}])

        final_count = db.session.scalar(
            select(func.count()).select_from(ProcessTable).filter(ProcessTable.workflow_id == wf_table.workflow_id)
        )
        assert initial_count == final_count
