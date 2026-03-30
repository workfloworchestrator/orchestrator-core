# Copyright 2019-2025 SURF, GÉANT, ESnet.
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
from collections.abc import Callable
from functools import partial
from uuid import UUID

import structlog
from psycopg import errors as psycopg_errors
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.db import ProcessTable, db
from orchestrator.utils.errors import ProcessAlreadyRunningError
from orchestrator.services.input_state import InputType, retrieve_input_state
from orchestrator.services.processes import (
    RESUME_WORKFLOW_REMOVED_ERROR_MSG,
    START_WORKFLOW_REMOVED_ERROR_MSG,
    SYSTEM_USER,
    StateMerger,
    _run_process_async,
    create_process,
    load_process,
    safe_logstep,
)
from orchestrator.types import BroadcastFunc
from orchestrator.workflow import (
    ProcessStat,
    ProcessStatus,
    StepLogFunc,
    runwf,
)
from orchestrator.workflows.removed_workflow import removed_workflow
from pydantic_forms.types import State

logger = structlog.get_logger(__name__)


def _set_process_status_running(process_id: UUID) -> None:
    """Set the process status to RUNNING to prevent it from being picked up by multiple workers.

    Uses SELECT FOR UPDATE NOWAIT wrapped in a SAVEPOINT so that lock contention does not abort
    an outer transaction (e.g. when called from within an active ``@step`` transaction).  If the
    row is already locked by another session, ``psycopg.errors.LockNotAvailable`` is raised by the
    driver, wrapped in ``sqlalchemy.exc.OperationalError``; we catch that, roll back the savepoint,
    and re-raise a descriptive exception without touching the outer transaction.

    Args:
        process_id: Process ID to fetch process from DB.

    Raises:
        ValueError: When the process row cannot be found.
        ProcessAlreadyRunningError: When the process is already in RUNNING status or locked by another worker.
    """
    stmt = select(ProcessTable).where(ProcessTable.process_id == process_id).with_for_update(nowait=True)

    try:
        with db.session.begin_nested():
            result = db.session.execute(stmt)
            locked_process = result.scalar_one_or_none()

            if not locked_process:
                raise ValueError(f"Process not found: {process_id}")

            if locked_process.last_status is not ProcessStatus.RUNNING:
                locked_process.last_status = ProcessStatus.RUNNING
            else:
                raise ProcessAlreadyRunningError(process_id)
    except OperationalError as e:
        if isinstance(e.orig, psycopg_errors.LockNotAvailable):
            raise ProcessAlreadyRunningError(process_id, reason="already being executed by another worker") from e
        raise
    else:
        db.session.commit()


def prepare_start(
    pstat: ProcessStat,
    broadcast_func: BroadcastFunc | None = None,
) -> tuple[ProcessStat, StepLogFunc]:
    """Prepare state for starting a workflow. Must run inside a database_scope.

    Retrieves initial input state, merges it into the process state, and marks the
    process as RUNNING. The commit in _set_process_status_running is the last DB
    operation, leaving no open transaction on the session's connection.

    Returns:
        Tuple of (updated ProcessStat, step log function) ready for runwf.
    """
    input_data = retrieve_input_state(pstat.process_id, "initial_state", False)
    pstat.update(state=pstat.state.map(lambda state: StateMerger.merge(state, input_data.input_state)))
    _set_process_status_running(pstat.process_id)
    return pstat, partial(safe_logstep, broadcast_func=broadcast_func)


def prepare_resume(
    process: ProcessTable,
    *,
    user: str | None = None,
    broadcast_func: BroadcastFunc | None = None,
) -> tuple[ProcessStat, StepLogFunc]:
    """Prepare state for resuming a workflow. Must run inside a database_scope.

    Loads the process state, retrieves user input, merges it, and marks the process
    as RUNNING. The commit in _set_process_status_running is the last DB operation,
    leaving no open transaction on the session's connection.

    Returns:
        Tuple of (ProcessStat, step log function) ready for runwf.
    """
    # ATTENTION!! When modifying this function make sure you make similar changes to `resume_workflow` in the test code
    pstat = load_process(process)
    if pstat.workflow == removed_workflow:
        raise ValueError(RESUME_WORKFLOW_REMOVED_ERROR_MSG)

    if user:
        pstat.update(current_user=user)

    # retrieve_input_str is for the edge case when workflow engine stops whilst there is an existing 'CREATED' process queue'ed.
    # It will have become a `RUNNING` process that gets resumed and this should fetch initial_state instead of user_input.
    retrieve_input_str: InputType = "user_input" if process.steps else "initial_state"
    input_data = retrieve_input_state(process.process_id, retrieve_input_str, False)
    pstat.update(state=pstat.state.map(lambda state: StateMerger.merge(state, input_data.input_state)))
    _set_process_status_running(process.process_id)
    return pstat, partial(safe_logstep, broadcast_func=broadcast_func)


def thread_start_process(
    pstat: ProcessStat,
    user: str = SYSTEM_USER,
    user_model: OIDCUserModel | None = None,
    broadcast_func: BroadcastFunc | None = None,
) -> UUID:
    if pstat.workflow == removed_workflow:
        raise ValueError(START_WORKFLOW_REMOVED_ERROR_MSG)

    pstat, logstep_func = prepare_start(pstat, broadcast_func=broadcast_func)
    return _run_process_async(pstat.process_id, lambda: runwf(pstat, logstep_func))


def thread_resume_process(
    process: ProcessTable,
    *,
    user: str | None = None,
    user_model: OIDCUserModel | None = None,
    broadcast_func: BroadcastFunc | None = None,
) -> UUID:
    pstat, logstep_func = prepare_resume(process, user=user, broadcast_func=broadcast_func)
    _run_process_async(pstat.process_id, lambda: runwf(pstat, logstep_func))
    return pstat.process_id


def thread_validate_workflow(validation_workflow: str, json: list[State] | None) -> UUID:
    pstat = create_process(validation_workflow, user_inputs=json)
    return thread_start_process(pstat)


THREADPOOL_EXECUTION_CONTEXT: dict[str, Callable] = {
    "start": thread_start_process,
    "resume": thread_resume_process,
    "validate": thread_validate_workflow,
}
