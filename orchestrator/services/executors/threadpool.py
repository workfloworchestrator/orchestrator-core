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
from sqlalchemy import select

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.db import ProcessTable, db
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
    runwf,
)
from orchestrator.workflows.removed_workflow import removed_workflow
from pydantic_forms.types import State

logger = structlog.get_logger(__name__)


def _set_process_status_running(process_id: UUID) -> None:
    """Set the process status to RUNNING to prevent it from being picked up by mutliple workers.

    uses with_for_update to lock the subscription in a transaction, preventing other changes.
    rolls back transation and raises an exception when its already on status RUNNING to prevent worker from running an already running process

    Args:
        process_id: Process ID to fetch process from DB
    """
    stmt = select(ProcessTable).where(ProcessTable.process_id == process_id).with_for_update()

    result = db.session.execute(stmt)
    locked_process = result.scalar_one_or_none()

    if not locked_process:
        db.session.rollback()
        raise ValueError(f"Process not found: {process_id}")

    if locked_process.last_status is not ProcessStatus.RUNNING:
        locked_process.last_status = ProcessStatus.RUNNING
        db.session.commit()
    else:
        db.session.rollback()
        raise Exception("Process is already running")


def thread_start_process(
    pstat: ProcessStat,
    user: str = SYSTEM_USER,
    user_model: OIDCUserModel | None = None,
    broadcast_func: BroadcastFunc | None = None,
) -> UUID:
    if pstat.workflow == removed_workflow:
        raise ValueError(START_WORKFLOW_REMOVED_ERROR_MSG)

    # enforce an update to the process status to properly show the process
    _set_process_status_running(pstat.process_id)

    input_data = retrieve_input_state(pstat.process_id, "initial_state", False)
    pstat.update(state=pstat.state.map(lambda state: StateMerger.merge(state, input_data.input_state)))

    _safe_logstep_with_func = partial(safe_logstep, broadcast_func=broadcast_func)
    return _run_process_async(pstat.process_id, lambda: runwf(pstat, _safe_logstep_with_func))


def thread_resume_process(
    process: ProcessTable,
    *,
    user: str | None = None,
    user_model: OIDCUserModel | None = None,
    broadcast_func: BroadcastFunc | None = None,
) -> UUID:
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

    # enforce an update to the process status to properly show the process
    _set_process_status_running(process.process_id)

    _safe_logstep_prep = partial(safe_logstep, broadcast_func=broadcast_func)
    _run_process_async(pstat.process_id, lambda: runwf(pstat, _safe_logstep_prep))
    return pstat.process_id


def thread_validate_workflow(validation_workflow: str, json: list[State] | None) -> UUID:
    pstat = create_process(validation_workflow, user_inputs=json)
    return thread_start_process(pstat)


THREADPOOL_EXECUTION_CONTEXT: dict[str, Callable] = {
    "start": thread_start_process,
    "resume": thread_resume_process,
    "validate": thread_validate_workflow,
}
