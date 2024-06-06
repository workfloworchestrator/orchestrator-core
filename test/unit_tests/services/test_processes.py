import asyncio
from http import HTTPStatus
from threading import Event
from time import sleep
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy import select

from orchestrator.config.assignee import Assignee
from orchestrator.db import ProcessStepTable, ProcessTable, db
from orchestrator.services.processes import (
    SYSTEM_USER,
    _async_resume_processes,
    _db_create_process,
    _db_log_process_ex,
    _db_log_step,
    _run_process_async,
    load_process,
    safe_logstep,
    start_process,
)
from orchestrator.services.settings import get_engine_settings
from orchestrator.settings import app_settings
from orchestrator.targets import Target
from orchestrator.utils.errors import ApiException, error_state_to_dict
from orchestrator.workflow import (
    Abort,
    Complete,
    Failed,
    ProcessStat,
    ProcessStatus,
    Skipped,
    StepList,
    StepStatus,
    Success,
    Suspend,
    Waiting,
    done,
    init,
    make_step_function,
    make_workflow,
    step,
    workflow,
)
from pydantic_forms.exceptions import FormValidationError
from test.unit_tests.workflows import WorkflowInstanceForTests, run_workflow, store_workflow


def _workflow_test_fn():
    pass


def _get_process_steps(process_id, *, order_by=None):
    stmt = select(ProcessStepTable).filter_by(process_id=process_id)
    if order_by is not None:
        stmt = stmt.order_by(order_by)
    return db.session.scalars(stmt).all()


@pytest.fixture
def simple_workflow():
    wf = make_workflow(_workflow_test_fn, "wf description", None, Target.SYSTEM, StepList())
    wf.name = "wf name"
    return store_workflow(wf)


def test_db_create_process(simple_workflow):
    process_id = uuid4()
    pstat = ProcessStat(process_id, simple_workflow, None, None, current_user="user")

    _db_create_process(pstat)

    process = db.session.get(ProcessTable, process_id)
    assert process
    assert process.workflow.name == "wf name"
    assert process.is_task


def test_process_log_db_step_success(simple_workflow):
    process_id = uuid4()
    p = ProcessTable(
        process_id=process_id,
        workflow_id=simple_workflow.workflow_id,
        last_status=ProcessStatus.CREATED,
        created_by=SYSTEM_USER,
    )
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(process_id, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"foo": "bar"}
    state = Success(state_data)

    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 1
    assert psteps[0].status == "success"
    assert psteps[0].process_id == process_id
    assert psteps[0].state == state_data
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.RUNNING
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"

    step = make_step_function(lambda: None, "step", None, "assignee")
    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 2
    assert psteps[1].status == "success"
    assert psteps[1].process_id == process_id
    assert psteps[1].state == state_data
    assert psteps[1].created_by == "user"
    assert p.last_status == ProcessStatus.RUNNING
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"


def test_process_log_db_step_skipped(simple_workflow):
    process_id = uuid4()
    p = ProcessTable(
        process_id=process_id,
        workflow_id=simple_workflow.workflow_id,
        last_status=ProcessStatus.CREATED,
        created_by=SYSTEM_USER,
    )
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(process_id, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"foo": "bar"}
    state = Skipped(state_data)

    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 1
    assert psteps[0].status == "skipped"
    assert psteps[0].process_id == process_id
    assert psteps[0].state == state_data
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.RUNNING
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"

    step = make_step_function(lambda: None, "step", None, "assignee")
    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 2
    assert psteps[1].status == "skipped"
    assert psteps[1].process_id == process_id
    assert psteps[1].state == state_data
    assert psteps[1].created_by == "user"
    assert p.last_status == ProcessStatus.RUNNING
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"


def test_process_log_db_step_suspend(simple_workflow):
    process_id = uuid4()
    p = ProcessTable(
        process_id=process_id,
        workflow_id=simple_workflow.workflow_id,
        last_status=ProcessStatus.CREATED,
        created_by=SYSTEM_USER,
    )
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(process_id, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"foo": "bar"}
    state = Suspend(state_data)

    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 1
    assert psteps[0].status == "suspend"
    assert psteps[0].process_id == process_id
    assert psteps[0].state == state_data
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.SUSPENDED
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"

    step = make_step_function(lambda: None, "step", None, "assignee")
    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 2
    assert psteps[1].status == "suspend"
    assert psteps[1].process_id == process_id
    assert psteps[1].state == state_data
    assert psteps[1].created_by == "user"
    assert p.last_status == ProcessStatus.SUSPENDED
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"


def test_process_log_db_step_waiting(simple_workflow):
    process_id = uuid4()
    p = ProcessTable(
        process_id=process_id,
        workflow_id=simple_workflow.workflow_id,
        last_status=ProcessStatus.CREATED,
        created_by=SYSTEM_USER,
    )
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(process_id, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = "expected failure"
    state = Waiting(error_state_to_dict(Exception(state_data)))

    result = _db_log_step(pstat, step, state)
    assert result.iswaiting()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 1
    assert psteps[0].status == "waiting"
    assert psteps[0].process_id == process_id
    assert psteps[0].state["error"] == state_data
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.WAITING
    assert p.last_step == "step"
    assert p.failed_reason == state_data
    assert p.assignee == "assignee"

    step = make_step_function(lambda: None, "step", None, "assignee")
    result = _db_log_step(pstat, step, state)
    assert result.iswaiting()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 1
    assert psteps[0].status == "waiting"
    assert psteps[0].process_id == process_id
    pstep_state = psteps[0].state
    assert len(pstep_state["executed_at"]) == 1
    del pstep_state["executed_at"]
    assert pstep_state == {"class": "Exception", "error": state_data, "retries": 1}
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.WAITING
    assert p.last_step == "step"
    assert p.failed_reason == state_data
    assert p.assignee == "assignee"


def test_process_log_db_step_failed(simple_workflow):
    process_id = uuid4()
    p = ProcessTable(
        process_id=process_id,
        workflow_id=simple_workflow.workflow_id,
        last_status=ProcessStatus.CREATED,
        created_by=SYSTEM_USER,
    )
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(process_id, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, Assignee.SYSTEM)

    state_data = Exception("Hard failure")
    state = Failed(state_data)

    result = _db_log_step(pstat, step, state.on_failed(error_state_to_dict))
    assert result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 1
    assert psteps[0].status == "failed"
    assert psteps[0].process_id == process_id
    saved_state = error_state_to_dict(state_data)
    saved_state.pop("traceback")
    assert psteps[0].state == saved_state
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.FAILED
    assert p.last_step == "step"
    assert p.failed_reason == "Hard failure"
    assert p.assignee == Assignee.SYSTEM

    step = make_step_function(lambda: None, "step", None, Assignee.SYSTEM)
    result = _db_log_step(pstat, step, state.on_failed(error_state_to_dict))
    assert result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 1
    assert psteps[0].status == "failed"
    assert psteps[0].process_id == process_id
    pstep_state = psteps[0].state
    assert len(pstep_state["executed_at"]) == 1
    del pstep_state["executed_at"]
    del pstep_state["class"]
    assert pstep_state == {"error": "Hard failure", "retries": 1}
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.FAILED
    assert p.last_step == "step"
    assert p.failed_reason == "Hard failure"
    assert p.assignee == Assignee.SYSTEM


def test_process_log_db_step_assertion_failed(simple_workflow):
    process_id = uuid4()
    p = ProcessTable(
        process_id=process_id,
        workflow_id=simple_workflow.workflow_id,
        last_status=ProcessStatus.CREATED,
        created_by=SYSTEM_USER,
        is_task=True,
    )
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(process_id, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")

    state_data = AssertionError("Assertion failure")
    state = Failed(state_data)

    result = _db_log_step(pstat, step, state.on_failed(error_state_to_dict))
    assert result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 1
    assert psteps[0].status == "failed"
    assert psteps[0].process_id == process_id
    saved_state = error_state_to_dict(state_data)
    saved_state.pop("traceback")
    assert psteps[0].state == saved_state
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.INCONSISTENT_DATA
    assert p.last_step == "step"
    assert p.failed_reason == "Assertion failure"
    assert p.assignee == Assignee.NOC

    step = make_step_function(lambda: None, "step", None, "assignee")
    result = _db_log_step(pstat, step, state.on_failed(error_state_to_dict))
    assert result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 1
    assert psteps[0].status == "failed"
    assert psteps[0].process_id == process_id
    pstep_state = psteps[0].state
    assert len(pstep_state["executed_at"]) == 1
    del pstep_state["executed_at"]
    del pstep_state["class"]
    assert pstep_state == {"error": "Assertion failure", "retries": 1}
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.INCONSISTENT_DATA
    assert p.last_step == "step"
    assert p.failed_reason == "Assertion failure"
    assert p.assignee == Assignee.NOC


def test_process_log_db_step_api_failed(simple_workflow):
    process_id = uuid4()
    p = ProcessTable(
        process_id=process_id,
        workflow_id=simple_workflow.workflow_id,
        last_status=ProcessStatus.CREATED,
        created_by=SYSTEM_USER,
        is_task=True,
    )
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(process_id, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")

    state_data = ApiException(HTTPStatus.BAD_GATEWAY, "API failure")
    state = Failed(state_data)

    result = _db_log_step(pstat, step, state.on_failed(error_state_to_dict))
    assert result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 1
    assert psteps[0].status == "failed"
    assert psteps[0].process_id == process_id
    saved_state = error_state_to_dict(state_data)
    saved_state.pop("traceback")
    assert psteps[0].state == saved_state
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.API_UNAVAILABLE
    assert p.last_step == "step"
    assert p.failed_reason == "API failure"
    assert p.assignee == Assignee.SYSTEM

    step = make_step_function(lambda: None, "step", None, "assignee")
    result = _db_log_step(pstat, step, state.on_failed(error_state_to_dict))
    assert result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 1
    assert psteps[0].status == "failed"
    assert psteps[0].process_id == process_id
    pstep_state = psteps[0].state
    assert len(pstep_state["executed_at"]) == 1
    del pstep_state["executed_at"]
    del pstep_state["class"]
    assert pstep_state == {
        "error": "API failure",
        "retries": 1,
        "headers": "",
        "status_code": HTTPStatus.BAD_GATEWAY,
        "body": None,
    }
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.API_UNAVAILABLE
    assert p.last_step == "step"
    assert p.failed_reason == "API failure"
    assert p.assignee == Assignee.SYSTEM


def test_process_log_db_step_abort(simple_workflow):
    process_id = uuid4()
    p = ProcessTable(
        process_id=process_id,
        workflow_id=simple_workflow.workflow_id,
        last_status=ProcessStatus.CREATED,
        created_by=SYSTEM_USER,
    )
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(process_id, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"foo": "bar"}
    state = Abort(state_data)

    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 1
    assert psteps[0].status == "abort"
    assert psteps[0].process_id == process_id
    assert psteps[0].state == state_data
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.ABORTED
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"

    step = make_step_function(lambda: None, "step", None, "assignee")
    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 2
    assert psteps[1].status == "abort"
    assert psteps[1].process_id == process_id
    assert psteps[1].state == state_data
    assert psteps[1].created_by == "user"
    assert p.last_status == ProcessStatus.ABORTED
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"


def test_process_log_db_step_complete(simple_workflow):
    process_id = uuid4()
    p = ProcessTable(
        process_id=process_id,
        workflow_id=simple_workflow.workflow_id,
        last_status=ProcessStatus.CREATED,
        created_by=SYSTEM_USER,
    )
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(process_id, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"foo": "bar"}
    state = Complete(state_data)

    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 1
    assert psteps[0].status == "complete"
    assert psteps[0].process_id == process_id
    assert psteps[0].state == state_data
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.COMPLETED
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"

    step = make_step_function(lambda: None, "step", None, "assignee")
    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = _get_process_steps(p.process_id)

    assert len(psteps) == 2
    assert psteps[1].status == "complete"
    assert psteps[1].process_id == process_id
    assert psteps[1].state == state_data
    assert psteps[1].created_by == "user"
    assert p.last_status == ProcessStatus.COMPLETED
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"


def test_process_log_db_step_no_process_id(simple_workflow):
    process_id = uuid4()

    pstat = ProcessStat(process_id, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"foo": "bar"}
    state = Complete(state_data)

    with pytest.raises(ValueError) as exc_info:
        _db_log_step(pstat, step, state)
    assert f"Failed to write failure step to process: process with PID {process_id} not found" in str(exc_info.value)


def test_process_log_db_step_deduplication(simple_workflow):
    process_id = uuid4()
    p = ProcessTable(
        process_id=process_id,
        workflow_id=simple_workflow.workflow_id,
        last_status=ProcessStatus.CREATED,
        created_by=SYSTEM_USER,
    )
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(process_id, None, None, None, current_user="user")

    step1 = make_step_function(lambda: None, "step1", None, Assignee.SYSTEM)
    step2 = make_step_function(lambda: None, "step2", None, Assignee.SYSTEM)
    error_state_data = {"error": "Soft failure"}
    _db_log_step(pstat, step1, Failed(error_state_data))
    _db_log_step(pstat, step2, Failed(error_state_data))
    _db_log_step(pstat, step1, Failed(error_state_data))
    _db_log_step(pstat, step1, Success({}))
    _db_log_step(pstat, step1, Failed(error_state_data))

    psteps = _get_process_steps(p.process_id, order_by=ProcessStepTable.executed_at.asc())

    assert psteps[0].name == "step1"
    assert psteps[0].status == "failed"
    assert psteps[0].state == error_state_data
    assert psteps[0].created_by == "user"

    assert psteps[1].name == "step2"
    assert psteps[1].status == "failed"
    assert psteps[1].state == error_state_data
    assert psteps[1].created_by == "user"

    assert psteps[2].name == "step1"
    assert psteps[2].status == "failed"
    assert psteps[2].state == error_state_data
    assert psteps[2].created_by == "user"

    assert psteps[3].name == "step1"
    assert psteps[3].status == "success"
    assert psteps[3].state == {}
    assert psteps[3].created_by == "user"

    assert psteps[4].name == "step1"
    assert psteps[4].status == "failed"
    assert psteps[4].state == error_state_data
    assert psteps[4].created_by == "user"

    assert len(psteps) == 5

    assert p.last_status == ProcessStatus.FAILED
    assert p.last_step == "step1"
    assert p.failed_reason == "Soft failure"
    assert p.assignee == Assignee.SYSTEM


def test_safe_logstep(simple_workflow):
    process_id = uuid4()
    p = ProcessTable(
        process_id=process_id,
        workflow_id=simple_workflow.workflow_id,
        last_status=ProcessStatus.CREATED,
        created_by=SYSTEM_USER,
    )
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(process_id, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"not_serializable": object()}
    state = Complete(state_data)

    with mock.patch("orchestrator.services.processes._db_log_step", spec=_db_log_step) as mock__db_log_step:
        mock__db_log_step.side_effect = [
            Exception("Failed to commit because of json serializable failure"),
            mock.sentinel.result,
        ]
        result = safe_logstep(pstat, step, state)

        assert result == mock.sentinel.result
        mock__db_log_step.assert_has_calls(
            [
                mock.call(
                    pstat,
                    step,
                    state,
                    None,  # broadcast_func, which is None for in-memory broadcasting
                ),
                mock.call(
                    pstat,
                    step,
                    Failed(
                        {
                            "class": "Exception",
                            "error": "Failed to commit because of json serializable failure",
                            "traceback": mock.ANY,
                        }
                    ),
                    None,  # broadcast_func, which is None for in-memory broadcasting
                ),
            ]
        )


def test_safe_logstep_critical_failure():
    process_id = uuid4()

    # Skip storing the actual process to let `_db_log_step` fail

    pstat = ProcessStat(process_id, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"not_serializable": object()}
    state = Complete(state_data)

    with mock.patch(  # Mock just to be able to spy on calls
        "orchestrator.services.processes._db_log_step", spec=_db_log_step, side_effect=_db_log_step
    ) as mock__db_log_step:
        with pytest.raises(ValueError) as e:
            result = safe_logstep(pstat, step, state)

            assert result == mock.sentinel.result

            mock__db_log_step.assert_has_calls(
                [
                    mock.call(pstat, step, state),
                    mock.call(
                        pstat,
                        step,
                        Failed(
                            {
                                "class": "Exception",
                                "error": f"Failed to write failure step to process: process with PID {process_id} not found",
                                "traceback": mock.ANY,
                            }
                        ),
                    ),
                ]
            )

        assert f"Failed to write failure step to process: process with PID {process_id} not found" in str(e.value)


@mock.patch("orchestrator.services.processes._get_process")
@mock.patch("orchestrator.services.processes.resume_process")
def test_async_resume_processes(mock_resume_process, mock_get_process, caplog):
    """Test that _async_resume_process() rejects running processes and handles failures."""
    processes = [
        mock.Mock(spec=ProcessTable()),
        mock.Mock(spec=ProcessTable()),
        mock.Mock(spec=ProcessTable()),
        mock.Mock(spec=ProcessTable()),
    ]
    processes[0].process_id, processes[0].last_status = 123, ProcessStatus.RUNNING
    processes[1].process_id, processes[1].last_status = 124, ProcessStatus.FAILED
    processes[2].process_id, processes[2].last_status = 125, ProcessStatus.API_UNAVAILABLE
    processes[3].process_id, processes[3].last_status = 126, ProcessStatus.RESUMED

    # get_process() should be called 4 times
    mock_get_process.side_effect = processes

    # resume_process() should be called 2 times for the non-running / non-resumed processes; let 1 call fail
    mock_resume_process.side_effect = [None, ValueError("This workflow cannot be resumed")]

    # Don't set app_settings.TESTING=False because we want to await the result
    asyncio.run(_async_resume_processes(processes, "testusername"))

    assert len(mock_get_process.mock_calls) == 4
    assert len(mock_resume_process.mock_calls) == 2
    assert "Cannot resume a running process" in caplog.text  # process_id 123 should not be resumed
    assert "Cannot resume a resumed process" in caplog.text  # process_id 126 should not be resumed
    assert "Failed to resume process" in caplog.text  # process_id 125 should fail
    assert "Completed resuming processes" in caplog.text


def test_db_log_process_ex(simple_workflow):
    process_id = uuid4()

    # No exceptions!
    _db_log_process_ex(process_id, ValueError())

    # Now with existing process
    p = ProcessTable(
        process_id=process_id,
        workflow_id=simple_workflow.workflow_id,
        last_status=ProcessStatus.CREATED,
        created_by=SYSTEM_USER,
    )
    db.session.add(p)
    db.session.commit()

    _db_log_process_ex(process_id, ValueError())

    assert p.last_status == "failed"


def test_run_process_async_success():
    process_id = uuid4()
    event = Event()

    def run_func():
        return Success(event.wait(1))

    # Disable Testing setting since we want to run async
    app_settings.TESTING = False
    _run_process_async(process_id, run_func)
    sleep(0.01)

    assert get_engine_settings().running_processes == 1

    event.set()
    sleep(1)

    assert get_engine_settings().running_processes == 0
    app_settings.TESTING = True


@mock.patch("orchestrator.services.processes._db_log_process_ex")
def test_run_process_async_exception(mock_db_log_process_ex):
    process_id = uuid4()
    event = Event()

    def run_func():
        event.wait(1)
        raise ValueError("Failed")

    # Disable Testing setting since we want to run async
    app_settings.TESTING = False
    _run_process_async(process_id, run_func)
    sleep(0.1)

    assert get_engine_settings().running_processes == 1

    event.set()
    sleep(0.1)

    assert get_engine_settings().running_processes == 0

    mock_db_log_process_ex.assert_called_once_with(process_id, mock.ANY)
    assert repr(mock_db_log_process_ex.call_args[0][1]) == "ValueError('Failed')"
    app_settings.TESTING = True


@mock.patch("orchestrator.services.processes._run_process_async", return_value=(mock.sentinel.process_id))
@mock.patch("orchestrator.services.processes._db_create_process")
@mock.patch("orchestrator.services.processes.post_form")
@mock.patch("orchestrator.services.processes.get_workflow")
def test_start_process(mock_get_workflow, mock_post_form, mock_db_create_process, mock_run_process_async):
    @step("test step")
    def test_step():
        pass

    wf = make_workflow(lambda: None, "description", None, Target.SYSTEM, [test_step])
    wf.name = "name"
    mock_get_workflow.return_value = wf

    mock_post_form.return_value = {"a": 1}

    result = start_process(mock.sentinel.wf_name, [{"a": 2}], mock.sentinel.user)

    pstat = mock_db_create_process.call_args[0][0]
    assert result == mock.sentinel.process_id
    assert pstat.current_user == mock.sentinel.user
    assert pstat.state.status == StepStatus.SUCCESS
    assert pstat.workflow == wf
    assert pstat.state.unwrap() == {
        "process_id": mock.ANY,
        "reporter": mock.sentinel.user,
        "workflow_name": mock.sentinel.wf_name,
        "workflow_target": Target.SYSTEM,
        "a": 1,
    }
    assert pstat.log == [test_step]
    mock_post_form.assert_called_once_with(
        mock.ANY,
        {
            "process_id": mock.ANY,
            "reporter": mock.sentinel.user,
            "workflow_name": mock.sentinel.wf_name,
            "workflow_target": Target.SYSTEM,
        },
        [{"a": 2}],
    )
    mock_get_workflow.assert_called_once_with(mock.sentinel.wf_name)

    mock_post_form.reset_mock()

    class MockEmptyValidationError:
        def errors(self):
            return []

    mock_post_form.side_effect = FormValidationError("", MockEmptyValidationError())

    with pytest.raises(FormValidationError):
        start_process(mock.sentinel.wf_name, None, mock.sentinel.user)
    mock_post_form.assert_called_once_with(
        mock.ANY,
        {
            "process_id": mock.ANY,
            "reporter": mock.sentinel.user,
            "workflow_name": mock.sentinel.wf_name,
            "workflow_target": Target.SYSTEM,
        },
        [{}],
    )


@step("Step 1")
def step1():
    return {"value": 1}


@step("Step 2")
def step2():
    return {"value": 2}


def get_step_names(process):
    return [fn.name for fn in process.log]


@pytest.mark.parametrize(
    "num_steps_finished,step_names",
    [
        (0, (["Start", "Step 1", "Done"], ["Start", "Step 1", "Step 2", "Done"], ["Start", "Done"])),
        (1, (["Step 1", "Done"], ["Step 1", "Step 2", "Done"], ["Done"])),
        (2, (["Done"], ["Step 2", "Done"], [])),  # WF with step removed is missing last step
        (3, ([], [], [])),  # WF is complete
    ],
)
def test_load_process_with_altered_steps(num_steps_finished, step_names):

    # Run original workflow with 3 steps
    with WorkflowInstanceForTests(workflow("Test wf")(lambda: init >> step1 >> done), "test_wf"):
        _, p_stat, steps = run_workflow("test_wf", [{}])
        process_table = db.session.get(ProcessTable, p_stat.process_id)

        for step_fn, wf_process in steps[:num_steps_finished]:
            process_table.steps.append(
                ProcessStepTable(
                    process_id=p_stat.process_id, name=step_fn.name, status=wf_process.status, state=wf_process.unwrap()
                )
            )

        process = load_process(process_table)
        assert get_step_names(process) == step_names[0]

    # Load process for workflow with step added at the end
    with WorkflowInstanceForTests(workflow("Test wf")(lambda: init >> step1 >> step2 >> done), "test_wf"):
        process = load_process(process_table)
        assert get_step_names(process) == step_names[1]

    # Load process for workflow with step removed at the end
    with WorkflowInstanceForTests(workflow("Test wf")(lambda: init >> done), "test_wf"):
        process = load_process(process_table)
        assert get_step_names(process) == step_names[2]
