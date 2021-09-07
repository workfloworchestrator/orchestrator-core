from concurrent.futures import Future
from http import HTTPStatus
from threading import Event
from time import sleep
from unittest import mock
from uuid import uuid4

import pytest

from orchestrator.config.assignee import Assignee
from orchestrator.db import EngineSettingsTable, ProcessStepTable, ProcessTable, db
from orchestrator.forms import FormValidationError
from orchestrator.services.processes import (
    SYSTEM_USER,
    _db_create_process,
    _db_log_process_ex,
    _db_log_step,
    _run_process_async,
    _safe_logstep,
    start_process,
)
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
    StepStatus,
    Success,
    Suspend,
    Waiting,
    make_step_function,
    make_workflow,
    step,
)


def test_db_create_process():
    pid = uuid4()
    workflow = make_workflow(lambda: None, "wf description", None, Target.SYSTEM, [])
    workflow.name = "wf name"
    pstat = ProcessStat(pid, workflow, None, None, current_user="user")

    _db_create_process(pstat)

    process = ProcessTable.query.get(pid)
    assert process
    assert process.workflow == "wf name"
    assert process.is_task


def test_process_log_db_step_success():
    pid = uuid4()
    p = ProcessTable(pid=pid, workflow="workflow_key", last_status=ProcessStatus.CREATED, created_by=SYSTEM_USER)
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(pid, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"foo": "bar"}
    state = Success(state_data)

    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 1
    assert psteps[0].status == "success"
    assert psteps[0].pid == pid
    assert psteps[0].state == state_data
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.RUNNING
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"

    step = make_step_function(lambda: None, "step", None, "assignee")
    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 2
    assert psteps[1].status == "success"
    assert psteps[1].pid == pid
    assert psteps[1].state == state_data
    assert psteps[1].created_by == "user"
    assert p.last_status == ProcessStatus.RUNNING
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"


def test_process_log_db_step_skipped():
    pid = uuid4()
    p = ProcessTable(pid=pid, workflow="workflow_key", last_status=ProcessStatus.CREATED, created_by=SYSTEM_USER)
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(pid, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"foo": "bar"}
    state = Skipped(state_data)

    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 1
    assert psteps[0].status == "skipped"
    assert psteps[0].pid == pid
    assert psteps[0].state == state_data
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.RUNNING
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"

    step = make_step_function(lambda: None, "step", None, "assignee")
    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 2
    assert psteps[1].status == "skipped"
    assert psteps[1].pid == pid
    assert psteps[1].state == state_data
    assert psteps[1].created_by == "user"
    assert p.last_status == ProcessStatus.RUNNING
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"


def test_process_log_db_step_suspend():
    pid = uuid4()
    p = ProcessTable(pid=pid, workflow="workflow_key", last_status=ProcessStatus.CREATED, created_by=SYSTEM_USER)
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(pid, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"foo": "bar"}
    state = Suspend(state_data)

    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 1
    assert psteps[0].status == "suspend"
    assert psteps[0].pid == pid
    assert psteps[0].state == state_data
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.SUSPENDED
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"

    step = make_step_function(lambda: None, "step", None, "assignee")
    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 2
    assert psteps[1].status == "suspend"
    assert psteps[1].pid == pid
    assert psteps[1].state == state_data
    assert psteps[1].created_by == "user"
    assert p.last_status == ProcessStatus.SUSPENDED
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"


def test_process_log_db_step_waiting():
    pid = uuid4()
    p = ProcessTable(pid=pid, workflow="workflow_key", last_status=ProcessStatus.CREATED, created_by=SYSTEM_USER)
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(pid, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = "expected failure"
    state = Waiting(error_state_to_dict(Exception(state_data)))

    result = _db_log_step(pstat, step, state)
    assert result.iswaiting()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 1
    assert psteps[0].status == "waiting"
    assert psteps[0].pid == pid
    assert psteps[0].state["error"] == state_data
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.WAITING
    assert p.last_step == "step"
    assert p.failed_reason == state_data
    assert p.assignee == "assignee"

    step = make_step_function(lambda: None, "step", None, "assignee")
    result = _db_log_step(pstat, step, state)
    assert result.iswaiting()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 1
    assert psteps[0].status == "waiting"
    assert psteps[0].pid == pid
    pstep_state = psteps[0].state
    assert len(pstep_state["executed_at"]) == 1
    del pstep_state["executed_at"]
    assert pstep_state == {"class": "Exception", "error": state_data, "retries": 1}
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.WAITING
    assert p.last_step == "step"
    assert p.failed_reason == state_data
    assert p.assignee == "assignee"


def test_process_log_db_step_failed():
    pid = uuid4()
    p = ProcessTable(pid=pid, workflow="workflow_key", last_status=ProcessStatus.CREATED, created_by=SYSTEM_USER)
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(pid, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, Assignee.SYSTEM)

    state_data = Exception("Hard failure")
    state = Failed(state_data)

    result = _db_log_step(pstat, step, state.on_failed(error_state_to_dict))
    assert result.isfailed()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 1
    assert psteps[0].status == "failed"
    assert psteps[0].pid == pid
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

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 1
    assert psteps[0].status == "failed"
    assert psteps[0].pid == pid
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


def test_process_log_db_step_assertion_failed():
    pid = uuid4()
    p = ProcessTable(
        pid=pid, workflow="workflow_key", last_status=ProcessStatus.CREATED, created_by=SYSTEM_USER, is_task=True
    )
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(pid, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")

    state_data = AssertionError("Assertion failure")
    state = Failed(state_data)

    result = _db_log_step(pstat, step, state.on_failed(error_state_to_dict))
    assert result.isfailed()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 1
    assert psteps[0].status == "failed"
    assert psteps[0].pid == pid
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

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 1
    assert psteps[0].status == "failed"
    assert psteps[0].pid == pid
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


def test_process_log_db_step_api_failed():
    pid = uuid4()
    p = ProcessTable(
        pid=pid, workflow="workflow_key", last_status=ProcessStatus.CREATED, created_by=SYSTEM_USER, is_task=True
    )
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(pid, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")

    state_data = ApiException(HTTPStatus.BAD_GATEWAY, "API failure")
    state = Failed(state_data)

    result = _db_log_step(pstat, step, state.on_failed(error_state_to_dict))
    assert result.isfailed()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 1
    assert psteps[0].status == "failed"
    assert psteps[0].pid == pid
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

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 1
    assert psteps[0].status == "failed"
    assert psteps[0].pid == pid
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


def test_process_log_db_step_abort():
    pid = uuid4()
    p = ProcessTable(pid=pid, workflow="workflow_key", last_status=ProcessStatus.CREATED, created_by=SYSTEM_USER)
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(pid, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"foo": "bar"}
    state = Abort(state_data)

    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 1
    assert psteps[0].status == "abort"
    assert psteps[0].pid == pid
    assert psteps[0].state == state_data
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.ABORTED
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"

    step = make_step_function(lambda: None, "step", None, "assignee")
    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 2
    assert psteps[1].status == "abort"
    assert psteps[1].pid == pid
    assert psteps[1].state == state_data
    assert psteps[1].created_by == "user"
    assert p.last_status == ProcessStatus.ABORTED
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"


def test_process_log_db_step_complete():
    pid = uuid4()
    p = ProcessTable(pid=pid, workflow="workflow_key", last_status=ProcessStatus.CREATED, created_by=SYSTEM_USER)
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(pid, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"foo": "bar"}
    state = Complete(state_data)

    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 1
    assert psteps[0].status == "complete"
    assert psteps[0].pid == pid
    assert psteps[0].state == state_data
    assert psteps[0].created_by == "user"
    assert p.last_status == ProcessStatus.COMPLETED
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"

    step = make_step_function(lambda: None, "step", None, "assignee")
    result = _db_log_step(pstat, step, state)
    assert not result.isfailed()

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).all()

    assert len(psteps) == 2
    assert psteps[1].status == "complete"
    assert psteps[1].pid == pid
    assert psteps[1].state == state_data
    assert psteps[1].created_by == "user"
    assert p.last_status == ProcessStatus.COMPLETED
    assert p.last_step == "step"
    assert p.failed_reason is None
    assert p.assignee == "assignee"


def test_process_log_db_step_no_pid():
    pid = uuid4()

    pstat = ProcessStat(pid, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"foo": "bar"}
    state = Complete(state_data)

    with pytest.raises(ValueError) as exc_info:
        _db_log_step(pstat, step, state)
    assert f"Failed to write failure step to process: process with PID {pid} not found" in str(exc_info.value)


def test_process_log_db_step_deduplication():
    pid = uuid4()
    p = ProcessTable(pid=pid, workflow="workflow_key", last_status=ProcessStatus.CREATED, created_by=SYSTEM_USER)
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(pid, None, None, None, current_user="user")

    step1 = make_step_function(lambda: None, "step1", None, Assignee.SYSTEM)
    step2 = make_step_function(lambda: None, "step2", None, Assignee.SYSTEM)
    error_state_data = {"error": "Soft failure"}
    _db_log_step(pstat, step1, Failed(error_state_data))
    _db_log_step(pstat, step2, Failed(error_state_data))
    _db_log_step(pstat, step1, Failed(error_state_data))
    _db_log_step(pstat, step1, Success({}))
    _db_log_step(pstat, step1, Failed(error_state_data))

    psteps = ProcessStepTable.query.filter_by(pid=p.pid).order_by(ProcessStepTable.executed_at.asc()).all()

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


def test_safe_logstep():
    pid = uuid4()
    p = ProcessTable(pid=pid, workflow="workflow_key", last_status=ProcessStatus.CREATED, created_by=SYSTEM_USER)
    db.session.add(p)
    db.session.commit()

    pstat = ProcessStat(pid, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"not_serializable": object()}
    state = Complete(state_data)

    with mock.patch("orchestrator.services.processes._db_log_step", spec=_db_log_step) as mock__db_log_step:

        mock__db_log_step.side_effect = [
            Exception("Failed to commit because of json serializable failure"),
            mock.sentinel.result,
        ]
        result = _safe_logstep(pstat, step, state)

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
                            "error": "Failed to commit because of json serializable failure",
                            "traceback": mock.ANY,
                        }
                    ),
                ),
            ]
        )


def test_safe_logstep_critical_failure():
    pid = uuid4()

    # Skip storing the actual process to let `_db_log_step` fail

    pstat = ProcessStat(pid, None, None, None, current_user="user")
    step = make_step_function(lambda: None, "step", None, "assignee")
    state_data = {"not_serializable": object()}
    state = Complete(state_data)

    with mock.patch(  # Mock just to be able to spy on calls
        "orchestrator.services.processes._db_log_step", spec=_db_log_step, side_effect=_db_log_step
    ) as mock__db_log_step:
        with pytest.raises(ValueError) as e:
            result = _safe_logstep(pstat, step, state)

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
                                "error": f"Failed to write failure step to process: process with PID {pid} not found",
                                "traceback": mock.ANY,
                            }
                        ),
                    ),
                ]
            )

        assert f"Failed to write failure step to process: process with PID {pid} not found" in str(e.value)


def test_db_log_process_ex():
    pid = uuid4()

    # No exceptions!
    _db_log_process_ex(pid, ValueError())

    # Now with existing process
    p = ProcessTable(pid=pid, workflow="workflow_key", last_status=ProcessStatus.CREATED, created_by=SYSTEM_USER)
    db.session.add(p)
    db.session.commit()

    _db_log_process_ex(pid, ValueError())

    assert p.last_status == "failed"


def test_run_process_async_success():
    pid = uuid4()
    event = Event()

    def run_func():
        return Success(event.wait(1))

    # Disable Testing setting since we want to run async
    app_settings.TESTING = False
    _run_process_async(pid, run_func)
    sleep(0.01)

    assert EngineSettingsTable.query.one().running_processes == 1

    event.set()
    sleep(1)

    assert EngineSettingsTable.query.one().running_processes == 0
    app_settings.TESTING = True


@mock.patch("orchestrator.services.processes._db_log_process_ex")
def test_run_process_async_exception(mock_db_log_process_ex):
    pid = uuid4()
    event = Event()

    def run_func():
        event.wait(1)
        raise ValueError("Failed")

    # Disable Testing setting since we want to run async
    app_settings.TESTING = False
    _run_process_async(pid, run_func)
    sleep(0.1)

    assert EngineSettingsTable.query.one().running_processes == 1

    event.set()
    sleep(0.1)

    assert EngineSettingsTable.query.one().running_processes == 0

    mock_db_log_process_ex.assert_called_once_with(pid, mock.ANY)
    assert repr(mock_db_log_process_ex.call_args[0][1]) == "ValueError('Failed')"
    app_settings.TESTING = True


@mock.patch("orchestrator.services.processes._run_process_async", return_value=(mock.sentinel.pid, Future()))
@mock.patch("orchestrator.services.processes._db_create_process")
@mock.patch("orchestrator.services.processes.post_process")
@mock.patch("orchestrator.services.processes.get_workflow")
def test_start_process(mock_get_workflow, mock_post_process, mock_db_create_process, mock_run_process_async):
    @step("test step")
    def test_step():
        pass

    wf = make_workflow(lambda: None, "description", None, Target.SYSTEM, [test_step])
    wf.name = "name"
    mock_get_workflow.return_value = wf

    mock_post_process.return_value = {"a": 1}

    result, _ = start_process(mock.sentinel.wf_name, [{"a": 2}], mock.sentinel.user)

    pstat = mock_db_create_process.call_args[0][0]
    assert result == mock.sentinel.pid
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
    mock_post_process.assert_called_once_with(
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

    mock_post_process.reset_mock()
    mock_post_process.side_effect = FormValidationError("", [])

    with pytest.raises(FormValidationError):
        start_process(mock.sentinel.wf_name, None, mock.sentinel.user)
    mock_post_process.assert_called_once_with(
        mock.ANY,
        {
            "process_id": mock.ANY,
            "reporter": mock.sentinel.user,
            "workflow_name": mock.sentinel.wf_name,
            "workflow_target": Target.SYSTEM,
        },
        [{}],
    )
