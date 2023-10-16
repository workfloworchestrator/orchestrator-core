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
from concurrent.futures.thread import ThreadPoolExecutor
from functools import partial
from http import HTTPStatus
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple
from uuid import UUID, uuid4

import structlog
from deepmerge import Merger
from fastapi import Request
from sqlalchemy.orm import joinedload

from nwastdlib.ex import show_ex
from orchestrator.api.error_handling import raise_status
from orchestrator.config.assignee import Assignee
from orchestrator.db import EngineSettingsTable, ProcessStepTable, ProcessSubscriptionTable, ProcessTable, db
from orchestrator.distlock import distlock_manager
from orchestrator.schemas.engine_settings import WorkerStatus
from orchestrator.settings import ExecutorType, app_settings
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
from orchestrator.workflow import (
    CALLBACK_TOKEN_KEY,
    Failed,
    ProcessStat,
    ProcessStatus,
    Step,
    StepList,
    Success,
    Workflow,
    abort_wf,
    runwf,
)
from orchestrator.workflow import Process as WFProcess
from orchestrator.workflows import get_workflow
from orchestrator.workflows.removed_workflow import removed_workflow
from pydantic_forms.core import post_form
from pydantic_forms.exceptions import FormValidationError

logger = structlog.get_logger(__name__)

StateMerger = Merger([(dict, ["merge"])], ["override"], ["override"])

SYSTEM_USER = "SYSTEM"

_workflow_executor = None


def get_execution_context() -> Dict[str, Callable]:
    if app_settings.EXECUTOR == ExecutorType.WORKER:
        from orchestrator.services.celery import CELERY_EXECUTION_CONTEXT

        return CELERY_EXECUTION_CONTEXT

    return THREADPOOL_EXECUTION_CONTEXT


def get_thread_pool() -> ThreadPoolExecutor:
    """Get and optionally initialise a ThreadPoolExecutor.

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
        process_id=stat.process_id,
        workflow_name=stat.workflow.name,
        last_status=ProcessStatus.CREATED,
        created_by=stat.current_user,
        is_task=stat.workflow.target == Target.SYSTEM,
    )
    db.session.add(p)
    db.session.commit()


def _update_process(process_id: UUID, step: Step, process_state: WFProcess) -> ProcessTable:
    p = ProcessTable.query.get(process_id)
    if p is None:
        raise ValueError(f"Failed to write failure step to process: process with PID {process_id} not found")

    p.last_step = step.name
    p.last_status = process_state.overall_status
    p.assignee = step.assignee
    step_state: State = process_state.unwrap()
    if process_state.isfailed() or process_state.iswaiting():
        failed_reason = step_state.get("error")
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
                in (
                    HTTPStatus.BAD_GATEWAY,
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    HTTPStatus.GATEWAY_TIMEOUT,
                )
            ):
                p.assignee = Assignee.SYSTEM
                p.last_status = ProcessStatus.API_UNAVAILABLE
            else:
                p.assignee = Assignee.SYSTEM

    else:
        p.failed_reason = None
        p.traceback = None

    return p


def _get_current_step_to_update(
    stat: ProcessStat, p: ProcessTable, step: Step, process_state: WFProcess
) -> ProcessStepTable:
    """Checks if last error state is identical to determine if we add a new step or update the last one.

    There are some special internal keys checked to customise how the step is updated in the database.
    These keys are only used for this purpose and not stored in the database.
    - '__step_name_override' - When this key is present, the value will be used as the ProcessStepTable.name
    - '__replace_last_state' - When the value for this key is truthy, the previous state in the db will be overridden
    - '__remove_keys' - Removes the keys in this given list from the state
    """
    step_state: State = process_state.unwrap()
    current_step = None
    last_db_step = p.steps[-1] if len(p.steps) else None

    # Core internal: __step_name_override
    step_name = step_state.pop("__step_name_override", step.name)

    # Core internal: __replace_last_state
    if step_state.pop("__replace_last_state", None):
        current_step = last_db_step
        current_step.status = process_state.status
        current_step.state = step_state

    # Core internal: __remove_keys
    try:
        keys_to_remove = step_state.get("__remove_keys", [])
        for k in keys_to_remove:
            step_state.pop(k, None)
    except TypeError:
        logger.error("Value for '__keys_to_remove' is not iterable.")
    finally:
        step_state.pop("__remove_keys", None)

    if process_state.isfailed() or process_state.iswaiting():
        if (
            last_db_step is not None
            and last_db_step.status == process_state.status
            and last_db_step.name == step.name
            and last_db_step.state.get("error") == step_state.get("error")
            and last_db_step.state.get("details") == step_state.get("details")
        ):
            state_ex_info = {
                "retries": last_db_step.state.get("retries", 0) + 1,
                "executed_at": last_db_step.state.get("executed_at", []) + [str(last_db_step.executed_at)],
            }

            # write new state info and execution date
            last_db_step.state = step_state | state_ex_info
            logger.info(
                "Updating existing process step with state info about the error",
                retries=state_ex_info["retries"],
            )
            current_step = last_db_step

    if current_step is None:
        # add a new entry to the process stat
        current_step = ProcessStepTable(
            process_id=stat.process_id,
            name=step_name,
            status=process_state.status,
            state=step_state,
            created_by=stat.current_user,
        )

    # Always explicitly set this instead of leaving it to the database to prevent failing tests
    # Test will fail if multiple steps have the same timestamp
    current_step.executed_at = nowtz()
    return current_step


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
        WFProcess: The process as stored in the database

    """
    p = _update_process(stat.process_id, step, process_state)
    current_step = _get_current_step_to_update(stat, p, step, process_state)

    db.session.add(p)
    db.session.add(current_step)
    try:
        db.session.commit()
    except BaseException:
        db.session.rollback()
        raise

    if websocket_manager.enabled:
        new_pStat = load_process(p)
        websocket_data = create_process_websocket_data(p, new_pStat)
        send_process_data_to_websocket(p.process_id, websocket_data, broadcast_func=broadcast_func)

    # Return the state as stored in the database
    return process_state.__class__(current_step.state)


def safe_logstep(
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


def _db_log_process_ex(process_id: UUID, ex: Exception) -> None:
    """Write the exception to the process or task when everything else has failed.

    Args:
        process_id: the process_id of the workflow process
        ex: the Exception message

    Returns: None, there is no one to listen at this point

    """

    p = ProcessTable.query.get(process_id)
    if p is None:
        logger.error(
            "Failed to write failure to database: Process with PID %s not found",
            process_id,
            process_id=process_id,
        )
        return

    logger.warning("Writing only process state to DB as step couldn't be found", process_id=process_id)
    p.last_step = "Unknown"
    if p.last_status != ProcessStatus.WAITING:
        p.last_status = ProcessStatus.FAILED
    p.failed_reason = str(ex)
    p.traceback = show_ex(ex)
    db.session.add(p)
    try:
        db.session.commit()
    except BaseException:
        logger.exception("Commit failed, rolling back", process_id=process_id)
        db.session.rollback()
        raise


def _get_process(process_id: UUID) -> ProcessTable:
    process = ProcessTable.query.options(
        joinedload(ProcessTable.steps),
        joinedload(ProcessTable.process_subscriptions).joinedload(ProcessSubscriptionTable.subscription),
    ).get(process_id)

    if not process:
        raise_status(HTTPStatus.NOT_FOUND, f"Process with process_id {process_id} not found")

    return process


def _run_process_async(process_id: UUID, f: Callable) -> UUID:
    def _update_running_processes(method: Literal["+", "-"], *args: Any) -> None:
        """Update amount of running processes by one.

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
                    logger.new(process_id=str(process_id))
                    result = f()
                except Exception as ex:
                    # We still have access to the database, so we can log at least something
                    _db_log_process_ex(process_id, ex)
                    raise
                finally:
                    _update_running_processes("-")
        except Exception as ex:
            # We lost access to database here, so we can only log
            logger.exception("Unknown workflow failure", process_id=process_id)
            result = Failed(ex)

        return result

    _update_running_processes("+")
    if app_settings.EXECUTOR == ExecutorType.THREADPOOL:
        workflow_executor = get_thread_pool()
        process_handle = workflow_executor.submit(run)

        # Wait for the thread to return.
        if app_settings.TESTING:
            process_handle.result()
    elif app_settings.EXECUTOR == ExecutorType.WORKER:
        # No need to run in a thread, just run.
        run()
    else:
        raise RuntimeError("Unknown Executor type")
    return process_id


def create_process(
    workflow_key: str,
    user_inputs: Optional[List[State]] = None,
    user: str = SYSTEM_USER,
) -> ProcessStat:
    # ATTENTION!! When modifying this function make sure you make similar changes to `run_workflow` in the test code

    if user_inputs is None:
        user_inputs = [{}]

    process_id = uuid4()
    workflow = get_workflow(workflow_key)

    if not workflow:
        raise_status(HTTPStatus.NOT_FOUND, "Workflow does not exist")

    initial_state = {
        "process_id": process_id,
        "reporter": user,
        "workflow_name": workflow_key,
        "workflow_target": workflow.target,
    }

    try:
        state = post_form(workflow.initial_input_form, initial_state, user_inputs)
    except FormValidationError:
        logger.exception("Validation errors", user_inputs=user_inputs)
        raise

    pstat = ProcessStat(
        process_id,
        workflow=workflow,
        state=Success(state | initial_state),
        log=workflow.steps,
        current_user=user,
    )

    _db_create_process(pstat)

    return pstat


def thread_start_process(
    workflow_key: str,
    user_inputs: Optional[List[State]] = None,
    user: str = SYSTEM_USER,
    broadcast_func: Optional[BroadcastFunc] = None,
) -> UUID:
    pstat = create_process(workflow_key, user_inputs=user_inputs, user=user)

    _safe_logstep_with_func = partial(safe_logstep, broadcast_func=broadcast_func)
    return _run_process_async(pstat.process_id, lambda: runwf(pstat, _safe_logstep_with_func))


def start_process(
    workflow_key: str,
    user_inputs: Optional[List[State]] = None,
    user: str = SYSTEM_USER,
    broadcast_func: Optional[BroadcastFunc] = None,
) -> UUID:
    """Start a process for workflow.

    Args:
        workflow_key: name of workflow
        user_inputs: List of form inputs from frontend
        user: User who starts this process
        broadcast_func: Optional function to broadcast process data

    Returns:
        process id

    """
    start_func = get_execution_context()["start"]
    return start_func(workflow_key, user_inputs=user_inputs, user=user, broadcast_func=broadcast_func)


def thread_resume_process(
    process: ProcessTable,
    *,
    user_inputs: Optional[List[State]] = None,
    user: Optional[str] = None,
    broadcast_func: Optional[BroadcastFunc] = None,
) -> UUID:
    # ATTENTION!! When modifying this function make sure you make similar changes to `resume_workflow` in the test code

    if user_inputs is None:
        user_inputs = [{}]

    pstat = load_process(process)

    if pstat.workflow == removed_workflow:
        raise ValueError("This workflow cannot be resumed")

    form = pstat.log[0].form

    user_input = post_form(form, pstat.state.unwrap(), user_inputs)

    if user:
        pstat.update(current_user=user)

    if user_input:
        pstat.update(state=pstat.state.map(lambda state: StateMerger.merge(state, user_input)))

    # enforce an update to the process status to properly show the process
    process.last_status = ProcessStatus.RUNNING
    db.session.add(process)
    db.session.commit()

    _safe_logstep_prep = partial(safe_logstep, broadcast_func=broadcast_func)
    return _run_process_async(pstat.process_id, lambda: runwf(pstat, _safe_logstep_prep))


def thread_validate_workflow(validation_workflow: str, json: Optional[List[State]]) -> UUID:
    return thread_start_process(validation_workflow, user_inputs=json)


THREADPOOL_EXECUTION_CONTEXT: Dict[str, Callable] = {
    "start": lambda *args, **kwargs: thread_start_process(*args, **kwargs),
    "resume": lambda *args, **kwargs: thread_resume_process(*args, **kwargs),
    "validate": thread_validate_workflow,
}


def resume_process(
    process: ProcessTable,
    *,
    user_inputs: Optional[List[State]] = None,
    user: Optional[str] = None,
    broadcast_func: Optional[BroadcastFunc] = None,
) -> UUID:
    """Resume a failed or suspended process.

    Args:
        process: Process from database
        user_inputs: Optional user input from forms
        user: user who resumed this process
        broadcast_func: Optional function to broadcast process data

    Returns:
        process id

    """
    pstat = load_process(process)
    try:
        post_form(pstat.log[0].form, pstat.state.unwrap(), user_inputs=user_inputs or [])
    except FormValidationError:
        logger.exception("Validation errors", user_inputs=user_inputs)
        raise

    resume_func = get_execution_context()["resume"]
    return resume_func(process, user_inputs=user_inputs, user=user, broadcast_func=broadcast_func)


def continue_awaiting_process(
    process: ProcessTable,
    *,
    token: str,
    input_data: State,
) -> UUID:
    """Continue a process awaiting data from a callback.

    Args:
        process: Process from database
        token: The token which was generated for the process. This must match.
        input_data: Data posted to the callback

    Returns:
        process id

    """

    pstat = load_process(process)
    state = pstat.state.unwrap()

    # Check if the token matches
    token_from_state = state.get(CALLBACK_TOKEN_KEY)
    if token != token_from_state:
        raise AssertionError("Invalid token")

    # We need to pass the callback data to the worker executor. Currently, this is not supported.
    # Therefore, we update the step state in the db and kick-off resume_workflow
    # Possible improvement: Allow passing additional data to be merged to the state upon resume_workflow
    result_key = state.get("__callback_result_key", "callback_result")
    state = {**state, result_key: input_data}

    current_step = process.steps[-1]
    current_step.state = state
    db.session.add(current_step)
    db.session.commit()

    # Continue the workflow
    resume_func = get_execution_context()["resume"]
    return resume_func(process)


async def _async_resume_processes(
    processes: List[ProcessTable],
    user_name: str,
    broadcast_func: Optional[Callable] = None,
) -> bool:
    """Asynchronously resume multiple failed processes.

    Args:
        processes: Processes from database
        user_name: User who requested resuming the processes
        broadcast_func: The broadcast functionality

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
                    process = _get_process(_proc.process_id)
                    if process.last_status == ProcessStatus.RUNNING:
                        # Process has been started by something else in the meantime
                        logger.info("Cannot resume a running process", process_id=_proc.process_id)
                        continue
                    elif process.last_status == ProcessStatus.RESUMED:  # noqa: RET507
                        # Process has been resumed by something else in the meantime
                        logger.info("Cannot resume a resumed process", process_id=_proc.process_id)
                        continue
                    resume_process(process, user=user_name, broadcast_func=broadcast_func)
                except Exception:
                    logger.exception("Failed to resume process", process_id=_proc.process_id)
            logger.info("Completed resuming processes")
        finally:
            distlock_manager.release_sync(lock)

    # Start all jobs in the background. BackgroundTasks might be more suited.
    workflow_executor = get_thread_pool()
    process_handle = workflow_executor.submit(run)
    if app_settings.TESTING:
        process_handle.result()
    return True


def abort_process(process: ProcessTable, user: str, broadcast_func: Optional[Callable] = None) -> WFProcess:
    pstat = load_process(process)

    pstat.update(current_user=user)
    return abort_wf(pstat, partial(safe_logstep, broadcast_func=broadcast_func))


def _recoverwf(wf: Workflow, log: List[WFProcess]) -> Tuple[WFProcess, StepList]:
    # Remove all extra steps (Failed, Suspended and (A)waiting steps in db). Only keep cleared steps.

    persistent = list(
        filter(lambda p: not (p.isfailed() or p.issuspend() or p.iswaiting() or p.isawaitingcallback()), log)
    )
    stepcount = len(persistent)

    if log and (log[-1].issuspend() or log[-1].isawaitingcallback()):
        # Use the state from the suspended/awaiting steps
        state = log[-1]
    elif persistent:
        # Otherwise, use the state from the last cleared step.
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
    workflow = get_workflow(process.workflow_name)

    if not workflow:
        workflow = removed_workflow

    log = _restore_log(process.steps)
    pstate, remaining = _recoverwf(workflow, log)

    return ProcessStat(
        process_id=process.process_id,
        workflow=workflow,
        state=pstate,
        log=remaining,
        current_user=SYSTEM_USER,
    )


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
                    process_id, data = self.queue.get(block=True, timeout=1)
                except queue.Empty:
                    continue
                logger.debug(
                    "Threadsafe broadcast data through websocket manager",
                    process_id=process_id,
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

    def _queue_put(process_id: UUID, data: Dict) -> None:
        broadcast_queue.put((str(process_id), data))

    return _queue_put


class ThreadPoolWorkerStatus(WorkerStatus):
    def __init__(self) -> None:
        super().__init__(executor_type="threadpool")
        thread_pool = get_thread_pool()
        self.number_of_workers_online = getattr(thread_pool, "_max_workers", -1)
        self.number_of_queued_jobs = thread_pool._work_queue.qsize() if hasattr(thread_pool, "_work_queue") else 0
        self.number_of_running_jobs = len(getattr(thread_pool, "_threads", []))
