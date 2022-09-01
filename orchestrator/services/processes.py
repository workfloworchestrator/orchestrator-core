# Copyright 2019-2020 SURF.
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
import asyncio
import queue
import threading
from concurrent.futures import Future
from concurrent.futures.thread import ThreadPoolExecutor
from functools import partial
from http import HTTPStatus
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple
from uuid import UUID, uuid4

import structlog
from deepmerge import Merger
from fastapi import Request
from nwastdlib.ex import show_ex
from sqlalchemy.orm import joinedload

from orchestrator.api.error_handling import raise_status
from orchestrator.config.assignee import Assignee
from orchestrator.db import EngineSettingsTable, ProcessStepTable, ProcessSubscriptionTable, ProcessTable, db
from orchestrator.distlock import distlock_manager
from orchestrator.forms import FormValidationError, post_process
from orchestrator.settings import app_settings
from orchestrator.targets import Target
from orchestrator.types import BroadcastFunc, State
from orchestrator.utils.datetime import nowtz
from orchestrator.utils.errors import error_state_to_dict
from orchestrator.websocket import (
    WS_CHANNELS,
    create_process_websocket_data,
    send_process_data_to_websocket,
    websocket_manager,
)
from orchestrator.websocket.websocket_manager import WebSocketManager
from orchestrator.workflow import Failed
from orchestrator.workflow import Process as WFProcess
from orchestrator.workflow import ProcessStat, ProcessStatus, Step, StepList, Success, Workflow, abort_wf, runwf
from orchestrator.workflows import get_workflow
from orchestrator.workflows.removed_workflow import removed_workflow

logger = structlog.get_logger(__name__)

StateMerger = Merger([(dict, ["merge"])], ["override"], ["override"])


SYSTEM_USER = "SYSTEM"


_workflow_executor = None


def get_thread_pool() -> ThreadPoolExecutor:
    """
    Get and optionally initialise a ThreadPoolExecutor.

    Returns:
        ThreadPoolExecutor

    """
    global _workflow_executor
    if _workflow_executor is None:
        _workflow_executor = ThreadPoolExecutor(max_workers=app_settings.MAX_WORKERS)
    return _workflow_executor


def shutdown_thread_pool() -> None:
    """Gracefully shutdown existing ThreadPoolExecutor and delete it."""
    global _workflow_executor
    if isinstance(_workflow_executor, ThreadPoolExecutor):
        _workflow_executor.shutdown(wait=True)
        _workflow_executor = None


def _db_create_process(stat: ProcessStat) -> None:
    p = ProcessTable(
        pid=stat.pid,
        workflow=stat.workflow.name,
        last_status=ProcessStatus.CREATED,
        created_by=stat.current_user,
        is_task=stat.workflow.target == Target.SYSTEM,
    )
    db.session.add(p)
    db.session.commit()


def _db_log_step(
    stat: ProcessStat,
    step: Step,
    process_state: WFProcess,
    broadcast_func: Optional[BroadcastFunc] = None,
) -> WFProcess:
    """Write the current step to the db.

    Args:
        stat: ProcessStat of process
        step: Current step
        process_state: State of process after current step
        broadcast_func: Optional function to broadcast process data

    Returns:
        WFProcess

    """
    p = ProcessTable.query.get(stat.pid)
    if p is None:
        raise ValueError(f"Failed to write failure step to process: process with PID {stat.pid} not found")

    p.last_step = step.name
    p.last_status = process_state.overall_status
    p.assignee = step.assignee

    step_state: State = process_state.unwrap()
    current_step = None
    if process_state.isfailed() or process_state.iswaiting():
        failed_reason = step_state.get("error")
        failed_details = step_state.get("details")
        # pop also removes the traceback from the dict
        traceback = step_state.pop("traceback", None)

        p.failed_reason = failed_reason
        p.traceback = traceback

        if process_state.isfailed() and p.is_task:
            # Check if we need a special failed status:
            # If it is an AssertionError:
            if step_state.get("class") == "AssertionError" or step_state.get("class") == "InconsistentData":
                p.assignee = Assignee.NOC
                p.last_status = ProcessStatus.INCONSISTENT_DATA
            # If we encounter a connectivity issue with an underlying api:
            elif step_state.get("class") == "MaxRetryError" or (
                step_state.get("class") == "ApiException"
                and step_state.get("status_code")
                in (HTTPStatus.BAD_GATEWAY, HTTPStatus.SERVICE_UNAVAILABLE, HTTPStatus.GATEWAY_TIMEOUT)
            ):
                p.assignee = Assignee.SYSTEM
                p.last_status = ProcessStatus.API_UNAVAILABLE
            else:
                p.assignee = Assignee.SYSTEM

        # check if last error state is identical to determine if we add a new step or update the last one
        last_db_step = p.steps[-1] if len(p.steps) else None

        if (
            last_db_step is not None
            and last_db_step.status == process_state.status
            and last_db_step.name == step.name
            and failed_reason == last_db_step.state.get("error")
            and failed_details == last_db_step.state.get("details")
        ):
            current_step = last_db_step

    else:
        p.failed_reason = None
        p.traceback = None

    db.session.add(p)

    if current_step is None:
        # add a new entry to the process stat
        logger.info("Adding a new process step with state info")
        current_step = ProcessStepTable(
            pid=stat.pid, name=step.name, status=process_state.status, state=step_state, created_by=stat.current_user
        )
    else:
        # update the last one with the repeated info
        retries = current_step.state.get("retries", 0) + 1
        executed_at = current_step.state.get("executed_at", [])
        executed_at.append(str(current_step.executed_at))

        # write new state info and execution date
        current_step.state = {**step_state, "retries": retries, "executed_at": executed_at}
        logger.info("Updating existing process step with state info about the error", retries=retries)

    # Always explicitly set this instead of leaving it to the database to prevent failing tests
    # Test will fail if multiple steps have the same timestamp
    current_step.executed_at = nowtz()

    db.session.add(current_step)
    try:
        db.session.commit()
    except BaseException:
        db.session.rollback()
        raise

    if websocket_manager.enabled:
        new_pStat = load_process(p)
        websocket_data = create_process_websocket_data(p, new_pStat)
        send_process_data_to_websocket(p.pid, websocket_data, broadcast_func=broadcast_func)

    # Return the state as stored in the database
    return process_state.__class__(current_step.state)


def _safe_logstep(
    stat: ProcessStat,
    step: Step,
    process_state: WFProcess,
    broadcast_func: Optional[BroadcastFunc] = None,
) -> WFProcess:
    """Log step and handle failures in logging.

    We need to be robust in failures to write steps to database. If that happens we try again with the failure.
    If that is also failing we give up by raising an exception which should be caught and written by _db_log_process_ex
    """

    try:
        return _db_log_step(stat, step, process_state, broadcast_func=broadcast_func)
    except Exception as e:
        logger.exception("Failed to save step", stat=stat, step=step, process_state=process_state)
        failure = Failed(error_state_to_dict(e))

        # Try writing the failure, but return the original exception on success
        # on a second failure the exception should be handled higher
        return _db_log_step(stat, step, failure, broadcast_func=broadcast_func)


def _db_log_process_ex(pid: UUID, ex: Exception) -> None:
    """
    Write the exception to the process or task when everything else has failed.

    Args:
        pid: the pid of the workflow process
        ex: the Exception message

    Returns: None, there is no one to listen at this point

    """

    p = ProcessTable.query.get(pid)
    if p is None:
        logger.error("Failed to write failure to database: Process with PID %s not found", pid, pid=pid)
        return

    logger.warning("Writing only process state to DB as step couldn't be found", pid=pid)
    p.last_step = "Unknown"
    if p.last_status != ProcessStatus.WAITING:
        p.last_status = ProcessStatus.FAILED
    p.failed_reason = str(ex)
    p.traceback = show_ex(ex)
    db.session.add(p)
    try:
        db.session.commit()
    except BaseException:
        logger.exception("Commit failed, rolling back", pid=pid)
        db.session.rollback()
        raise


def _get_process(pid: UUID) -> ProcessTable:
    process = ProcessTable.query.options(
        joinedload(ProcessTable.steps),
        joinedload(ProcessTable.process_subscriptions).joinedload(ProcessSubscriptionTable.subscription),
    ).get(pid)

    if not process:
        raise_status(HTTPStatus.NOT_FOUND, f"Process with pid {pid} not found")

    return process


def _run_process_async(pid: UUID, f: Callable) -> Tuple[UUID, Future]:
    def _update_running_processes(method: Literal["+", "-"], *args: Any) -> None:
        """
        Update amount of running processes by one.

        Args:
            method: Add or subtract by one the amount of running processes
            args: Any args that are still going to be passed. When called as a callback this will be the future.
        Returns:
            None

        """
        engine_settings = EngineSettingsTable.query.with_for_update().one()
        engine_settings.running_processes += 1 if method == "+" else -1
        if engine_settings.running_processes < 0:
            engine_settings.running_processes = 0
        db.session.commit()

    def run() -> WFProcess:
        try:
            with db.database_scope():
                try:
                    logger.new(process_id=str(pid))
                    result = f()
                except Exception as ex:
                    # We still have access to the database, so we can log at least something
                    _db_log_process_ex(pid, ex)
                    raise
                finally:
                    _update_running_processes("-")
        except Exception as ex:
            # We lost access to database here so we can only log
            logger.exception("Unknown workflow failure", pid=pid)
            result = Failed(ex)

        return result

    workflow_executor = get_thread_pool()

    process_handle = workflow_executor.submit(run)
    _update_running_processes("+")

    if app_settings.TESTING:
        process_handle.result()

    return pid, process_handle


def start_process(
    workflow_key: str,
    user_inputs: Optional[List[State]] = None,
    user: str = SYSTEM_USER,
    broadcast_func: Optional[BroadcastFunc] = None,
) -> Tuple[UUID, Future]:
    """Start a process for workflow.

    Args:
        workflow_key: name of workflow
        user_inputs: List of form inputs from frontend
        user: User who starts this process
        broadcast_func: Optional function to broadcast process data

    Returns:
        process id

    """
    # ATTENTION!! When modifying this function make sure you make similar changes to `run_workflow` in the test code

    if user_inputs is None:
        user_inputs = [{}]

    pid = uuid4()
    workflow = get_workflow(workflow_key)

    if not workflow:
        raise_status(HTTPStatus.NOT_FOUND, "Workflow does not exist")

    initial_state = {
        "process_id": pid,
        "reporter": user,
        "workflow_name": workflow_key,
        "workflow_target": workflow.target,
    }

    try:
        state = post_process(workflow.initial_input_form, initial_state, user_inputs)
    except FormValidationError:
        logger.exception("Validation errors", user_inputs=user_inputs)
        raise

    pstat = ProcessStat(
        pid, workflow=workflow, state=Success({**state, **initial_state}), log=workflow.steps, current_user=user
    )

    _db_create_process(pstat)

    _safe_logstep_withfunc = partial(_safe_logstep, broadcast_func=broadcast_func)
    return _run_process_async(pstat.pid, lambda: runwf(pstat, _safe_logstep_withfunc))


def resume_process(
    process: ProcessTable,
    *,
    user_inputs: Optional[List[State]] = None,
    user: Optional[str] = None,
    broadcast_func: Optional[BroadcastFunc] = None,
) -> Tuple[UUID, Future]:
    """Resume a failed or suspended process.

    Args:
        process: Process from database
        user_inputs: Optional user input from forms
        user: user who resumed this process
        broadcast_func: Optional function to broadcast process data

    Returns:
        process id

    """
    # ATTENTION!! When modifying this function make sure you make similar changes to `resume_workflow` in the test code

    if user_inputs is None:
        user_inputs = [{}]

    pstat = load_process(process)

    if pstat.workflow == removed_workflow:
        raise ValueError("This workflow cannot be resumed")

    form = pstat.log[0].form

    user_input = post_process(form, pstat.state.unwrap(), user_inputs)

    if user:
        pstat.update(current_user=user)

    if user_input:
        pstat.update(state=pstat.state.map(lambda state: StateMerger.merge(state, user_input)))

    # enforce an update to the process status to properly show the process
    process.last_status = ProcessStatus.RUNNING
    db.session.add(process)
    db.session.commit()

    _safe_logstep_prep = partial(_safe_logstep, broadcast_func=broadcast_func)
    return _run_process_async(pstat.pid, lambda: runwf(pstat, _safe_logstep_prep))


async def _async_resume_processes(
    processes: List[ProcessTable], user_name: str, broadcast_func: Optional[Callable] = None
) -> bool:
    """Asynchronously resume multiple failed processes.

    Args:
        processes: Processes from database
        user_name: User who requested resuming the processes

    Returns:
        True if the resume-all operation has been started.
        False if it has not been started because it is already running.

    """
    lock_expiration = max(30, len(processes) // 10)
    if not (lock := await distlock_manager.get_lock("resume-all", lock_expiration)):
        return False

    def run() -> None:
        try:
            for _proc in processes:
                try:
                    process = _get_process(_proc.pid)
                    if process.last_status == ProcessStatus.RUNNING:
                        # Process has been started by something else in the meantime
                        logger.info("Cannot resume a running process", pid=_proc.pid)
                        continue
                    resume_process(process, user=user_name, broadcast_func=broadcast_func)
                except Exception:
                    logger.exception("Failed to resume process", pid=_proc.pid)
            logger.info("Completed resuming processes")
        finally:
            distlock_manager.release_sync(lock)  # type: ignore

    workflow_executor = get_thread_pool()

    process_handle = workflow_executor.submit(run)

    if app_settings.TESTING:
        process_handle.result()

    return True


def abort_process(process: ProcessTable, user: str, broadcast_func: Optional[Callable] = None) -> WFProcess:
    pstat = load_process(process)

    pstat.update(current_user=user)
    return abort_wf(pstat, partial(_safe_logstep, broadcast_func=broadcast_func))


def _recoverwf(wf: Workflow, log: List[WFProcess]) -> Tuple[WFProcess, StepList]:
    # Remove all extra steps (Failed, Suspended and Waiting steps add extra steps in db)
    persistent = list(filter(lambda p: not (p.isfailed() or p.issuspend() or p.iswaiting()), log))
    stepcount = len(persistent)

    # Make sure we get the last state from the suspend step (since we removed it before)
    if log and log[-1].issuspend():
        state = log[-1]
    elif persistent:
        state = persistent[-1]
    else:
        state = Success({})

    rest = wf.steps[stepcount:]

    return state, rest


def _restore_log(steps: List[ProcessStepTable]) -> List[WFProcess]:
    result = []
    for step in steps:
        process = WFProcess.from_status(step.status, step.state)

        if not process:
            raise ValueError(step.status)

        result.append(process)
    return result


def load_process(process: ProcessTable) -> ProcessStat:
    workflow = get_workflow(process.workflow)

    if not workflow:
        workflow = removed_workflow

    log = _restore_log(process.steps)
    pstate, remaining = _recoverwf(workflow, log)

    return ProcessStat(pid=process.pid, workflow=workflow, state=pstate, log=remaining, current_user=SYSTEM_USER)


class ProcessDataBroadcastThread(threading.Thread):
    def __init__(self, _websocket_manager: WebSocketManager, *args, **kwargs) -> None:  # type: ignore
        super().__init__(*args, **kwargs)
        self.shutdown = False
        self.queue: queue.Queue = queue.Queue()
        self.websocket_manager = _websocket_manager

    def run(self) -> None:
        logger.info("Starting ProcessDataBroadcastThread")
        try:
            loop = asyncio.new_event_loop()  # Create an eventloop specifically for this thread

            while not self.shutdown:
                try:
                    pid, data = self.queue.get(block=True, timeout=1)
                except queue.Empty:
                    continue
                logger.debug(
                    "Threadsafe broadcast data through websocket manager",
                    process_id=pid,
                    where="ProcessDataBroadcastThread",
                    channels=WS_CHANNELS.ALL_PROCESSES,
                )
                loop.run_until_complete(self.websocket_manager.broadcast_data([WS_CHANNELS.ALL_PROCESSES], data))

            loop.close()
            logger.info("Shutdown ProcessDataBroadcastThread")
        except Exception:
            logger.exception("Unhandled exception in ProcessDataBroadcastThread, exiting")

    def stop(self) -> None:
        logger.debug("Sending shutdown signal to ProcessDataBroadcastThread")
        self.shutdown = True
        self.join(timeout=5)
        self.is_alive()


def api_broadcast_process_data(request: Request) -> Optional[BroadcastFunc]:
    """Given a FastAPI request, creates a threadsafe callable for broadcasting process data.

    The callable should be created in API endpoints and provided to start_process,
    resume_process, etc. through the `broadcast_func` param.
    """
    broadcast_queue: queue.Queue = request.app.broadcast_thread.queue

    def _queue_put(pid: UUID, data: Dict) -> None:
        broadcast_queue.put((str(pid), data))

    return _queue_put
