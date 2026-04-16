# Copyright 2019-2026 SURF, GÉANT, ESnet.
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
    """Set the process status to RUNNING to prevent multiple workers from picking it up.

    Uses ``with_for_update`` to lock the process row for the duration of the enclosing
    transaction, preventing concurrent workers from racing on the same process. Must be
    called inside an active ``session.begin()`` block — the caller owns commit/rollback
    semantics, this function only stages the ORM mutation and raises on precondition
    failures.

    Args:
        process_id: Process ID to fetch from DB.

    Raises:
        ValueError: If the process is not found.
        RuntimeError: If the process is already RUNNING (indicates a duplicate worker).
    """
    stmt = select(ProcessTable).where(ProcessTable.process_id == process_id).with_for_update()

    result = db.session.execute(stmt)
    locked_process = result.scalar_one_or_none()

    if not locked_process:
        raise ValueError(f"Process not found: {process_id}")

    if locked_process.last_status is ProcessStatus.RUNNING:
        raise RuntimeError("Process is already running")

    locked_process.last_status = ProcessStatus.RUNNING


def prepare_start_state(pstat: ProcessStat) -> ProcessStat:
    """Mark a process RUNNING and merge its initial input state into the pstat.

    Must be called inside an open :func:`database_scope` with an active
    :meth:`Session.begin` transaction. Performs the pre-execution DB reads that
    every workflow start needs, in a way that can be hoisted into a caller's
    single consolidated scope (see ``services/tasks.py::start_process``) or
    wrapped by ``thread_start_process``'s backwards-compat fast-path for direct
    callers such as ``thread_validate_workflow``.

    Args:
        pstat: The in-memory ProcessStat to enrich with the initial state.

    Returns:
        A new ProcessStat whose state is the merge of the incoming pstat state
        with the initial input state loaded from the database.
    """
    _set_process_status_running(pstat.process_id)
    input_data = retrieve_input_state(pstat.process_id, "initial_state", False)
    initial_state: dict = dict(input_data.input_state) if input_data else {}
    return pstat.update(state=pstat.state.map(lambda state: StateMerger.merge(state, initial_state)))


def prepare_resume_state(process: ProcessTable, user: str | None = None) -> ProcessStat:
    """Load the process, mark it RUNNING, and return a pstat with resume state merged.

    Must be called inside an open :func:`database_scope` with an active
    :meth:`Session.begin` transaction. Loads the :class:`ProcessStat` from the
    ORM row, validates that the workflow is not the removed sentinel, marks
    the process RUNNING, reads the resume input state (either ``user_input``
    or ``initial_state`` depending on whether steps have already executed),
    and deep-merges it into ``pstat.state`` via :data:`StateMerger`.

    Args:
        process: The ORM :class:`ProcessTable` row being resumed.
        user: Optional user identifier to stamp onto ``pstat.current_user``.

    Returns:
        A fully-prepared :class:`ProcessStat` ready to be dispatched to
        :func:`_run_process_async`.
    """
    pstat = load_process(process)
    if pstat.workflow == removed_workflow:
        raise ValueError(RESUME_WORKFLOW_REMOVED_ERROR_MSG)

    # retrieve_input_str is for the edge case when the workflow engine stops whilst
    # there is an existing 'CREATED' process queued. It will have become a 'RUNNING'
    # process that gets resumed and should fetch initial_state instead of user_input.
    retrieve_input_str: InputType = "user_input" if process.steps else "initial_state"
    input_data = retrieve_input_state(process.process_id, retrieve_input_str, False)
    resume_state: dict = dict(input_data.input_state) if input_data else {}

    _set_process_status_running(process.process_id)

    if user:
        pstat = pstat.update(current_user=user)
    return pstat.update(state=pstat.state.map(lambda state: StateMerger.merge(state, resume_state)))


def thread_start_process(
    pstat: ProcessStat,
    user: str = SYSTEM_USER,
    user_model: OIDCUserModel | None = None,
    broadcast_func: BroadcastFunc | None = None,
    _prepared: bool = False,
) -> UUID:
    """Dispatch a workflow start. See :func:`prepare_start_state` for the pre-work.

    When called via ``services/tasks.py::start_process`` (the Celery path), the
    caller has already run :func:`prepare_start_state` inside its own consolidated
    scope and passes ``_prepared=True`` so this function becomes dispatch-only.
    Direct callers like :func:`thread_validate_workflow` pass ``_prepared=False``
    (the default) and this function opens its own scope as a backwards-compat path.
    """
    if pstat.workflow == removed_workflow:
        raise ValueError(START_WORKFLOW_REMOVED_ERROR_MSG)

    if not _prepared:
        # Backwards-compat path for direct callers that have not yet opened a scope.
        with db.database_scope(), db.session.begin():
            pstat = prepare_start_state(pstat)

    _safe_logstep_with_func = partial(safe_logstep, broadcast_func=broadcast_func)
    return _run_process_async(pstat.process_id, lambda: runwf(pstat, _safe_logstep_with_func))


def thread_resume_process(
    process: ProcessTable,
    *,
    user: str | None = None,
    user_model: OIDCUserModel | None = None,
    broadcast_func: BroadcastFunc | None = None,
    _prepared_pstat: ProcessStat | None = None,
) -> UUID:
    """Dispatch a workflow resume. See :func:`prepare_resume_state` for the pre-work.

    When called via ``services/tasks.py::resume_process`` (the Celery path), the
    caller has already loaded and prepared the pstat inside its own consolidated
    scope and passes it via ``_prepared_pstat``. Direct callers pass ``None``
    (the default) and this function opens its own scope as a backwards-compat path.
    """
    # ATTENTION!! When modifying this function make sure you make similar changes to `resume_workflow` in the test code
    if _prepared_pstat is not None:
        pstat = _prepared_pstat
    else:
        with db.database_scope(), db.session.begin():
            pstat = prepare_resume_state(process, user=user)

    _safe_logstep_prep = partial(safe_logstep, broadcast_func=broadcast_func)
    _run_process_async(pstat.process_id, lambda: runwf(pstat, _safe_logstep_prep))
    return pstat.process_id


def thread_validate_workflow(validation_workflow: str, json: list[State] | None) -> UUID:
    """Create, prepare, and asynchronously start a validation workflow process.

    Opens its own :func:`~orchestrator.db.database_scope` so that
    :func:`create_process`'s commits (in :func:`_db_create_process` and
    :func:`store_input_state`) are real — not silenced by any enclosing
    :func:`~orchestrator.db.database.disable_commit` guard that step bodies
    activate.  Only after those rows are durably committed can
    :func:`prepare_start_state`'s ``SELECT … FOR UPDATE`` find the process.
    """
    with db.database_scope():
        pstat = create_process(validation_workflow, user_inputs=json)
        with db.session.begin():
            pstat = prepare_start_state(pstat)
    return thread_start_process(pstat, _prepared=True)


THREADPOOL_EXECUTION_CONTEXT: dict[str, Callable] = {
    "start": thread_start_process,
    "resume": thread_resume_process,
    "validate": thread_validate_workflow,
}
