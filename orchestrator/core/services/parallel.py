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

"""Parallel branch execution support for distributed workers.

Handles:
- Executing a single branch in a worker task
- Atomic join counter (UPDATE...RETURNING)
- Last-finisher detection and parent workflow resumption
"""

from __future__ import annotations

from copy import deepcopy
from uuid import UUID

import structlog
from more_itertools import unique_everseen
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload

from orchestrator.core.db import ProcessStepTable, ProcessTable, db
from orchestrator.core.db.database import transactional
from orchestrator.core.db.models import ProcessStepRelationTable
from orchestrator.core.workflow import (
    _STATUSES,
    ProcessStat,
    Step,
    StepList,
    StepStatus,
    Success,
    Workflow,
    _exec_steps,
    _find_step_by_group_name,
    _make_branch_dblogstep,
    _worst_status,
    process_stat_var,
    reconstruct_branch,
)

logger = structlog.get_logger(__name__)


def _atomic_increment_completed(fork_step_id: UUID) -> tuple[int, int | None]:
    """Atomically increment branches_completed and return (new_count, branch_count).

    Uses UPDATE...RETURNING for atomic last-finisher detection, avoiding an extra SELECT. Does not commit: the row
    lock taken by the UPDATE is held until :func:`run_worker_branch` commits, so the last finisher can update the fork
    row in the same transaction.
    """
    stmt = (
        update(ProcessStepTable)
        .where(ProcessStepTable.step_id == fork_step_id)
        .values(branches_completed=ProcessStepTable.branches_completed + 1)
        .returning(ProcessStepTable.branches_completed, ProcessStepTable.branch_count)
    )
    result = db.session.execute(stmt)
    completed, total = result.one()
    return completed, total


def _collect_branch_results(fork_step_id: UUID) -> list[tuple[int, dict, str]]:
    """Collect branch results from DB via ProcessStepRelationTable.

    Returns list of (branch_index, state, status) sorted by branch_index.
    Takes the last step per branch (highest order_id) as the branch result.
    """
    stmt = (
        select(ProcessStepRelationTable)
        .where(ProcessStepRelationTable.parent_step_id == fork_step_id)
        .options(joinedload(ProcessStepRelationTable.child_step))
        .order_by(ProcessStepRelationTable.branch_index, ProcessStepRelationTable.order_id.desc())
    )
    relations = db.session.execute(stmt).scalars().all()

    # TODO convert status with Process(StepStatus(rel.child_step.status), state) as that is what callers use
    first_per_branch = unique_everseen(relations, key=lambda r: r.branch_index)
    return [(rel.branch_index, rel.child_step.state, rel.child_step.status) for rel in first_per_branch]


def _succeeded_branch_indices(fork_step_id: UUID) -> set[int]:
    """Return the set of branch indices whose most recent attempt succeeded.

    Used by retry logic to skip branches that already completed successfully
    on a previous attempt of the same parallel group.
    """
    return {idx for idx, _state, status in _collect_branch_results(fork_step_id) if status == StepStatus.SUCCESS}


def _find_parallel_step(steps: StepList, group_name: str) -> Step | None:
    """Recursively search steps (and their parallel branches) for a parallel group name.

    Walks the step tree depth-first, checking each step's ``_parallel_group_name``
    attribute. Also recurses into ``_parallel_branches`` (static parallel) and
    ``_foreach_branch_template`` (dynamic parallel).

    Group names are unique within a workflow, validated when the workflow is built by
    :func:`_validate_unique_parallel_group_names`, so there is exactly one match. Without that check this
    first-match lookup could rebuild a branch from a different parallel step with the same name.

    Args:
        steps: A StepList (iterable of Step functions) to search.
        group_name: The parallel group name to find.

    Returns:
        The Step with matching ``_parallel_group_name``, or None if not found.
    """
    # TODO make step metadata check type-safe
    return _find_step_by_group_name(steps, group_name)


def _resolve_branch_from_db(
    fork_step_id: UUID, process_id: UUID, branch_index: int
) -> tuple[str, StepList, ProcessTable, Workflow]:
    """Derive the workflow key, branch step list, process, and workflow from the fork step in DB.

    The fork step's ``name`` stores the parallel group name, and the process's
    workflow relationship provides the workflow key. This avoids passing workflow
    metadata through the Celery task arguments.

    Returns:
        (parallel_group_name, branch_step_list, process, workflow)
    """
    from orchestrator.core.workflows import get_workflow

    # TODO select step name directly by fork_step_id
    fork_step = db.session.get(ProcessStepTable, fork_step_id)
    if fork_step is None:
        raise ValueError(f"Fork step {fork_step_id} not found")

    parallel_group_name = fork_step.name

    # TODO select workflow name directly by process_id
    #  Remove `process` from return values as it's unused
    process = db.session.get(ProcessTable, process_id)
    if process is None:
        raise ValueError(f"Process {process_id} not found")

    workflow_key = process.workflow.name
    wf = get_workflow(workflow_key)
    if wf is None:
        raise ValueError(f"Workflow '{workflow_key}' not found")

    parallel_step = _find_parallel_step(wf.steps, parallel_group_name)
    if parallel_step is None:
        raise ValueError(f"Parallel group '{parallel_group_name}' not found in workflow '{workflow_key}'")

    return parallel_group_name, reconstruct_branch(parallel_step, branch_index), process, wf


def run_worker_branch(
    *,
    process_id: UUID,
    branch_index: int,
    fork_step_id: UUID,
    initial_state: dict,
    user: str,
    seed_state: dict | None = None,
) -> None:
    """Execute a single parallel branch in a distributed worker.

    Derives the workflow key and parallel group name from the fork step in DB,
    then executes the branch with DB logging. After execution, atomically
    increments the completed counter. If this is the last branch, collects all
    results and resolves the fork step.

    The increment and, for the last branch, the fork update run in one
    transaction that is committed exactly once, right before the parent workflow
    is resumed.
    """
    parallel_group_name, branch, process, wf = _resolve_branch_from_db(fork_step_id, process_id, branch_index)

    # Set process_stat_var so nested parallel branches can create fork steps
    # and dispatch to Celery workers (if EXECUTOR=WORKER).
    pstat = ProcessStat(
        process_id=process_id,
        workflow=wf,
        state=Success(initial_state),
        log=wf.steps,
        current_user=user,
    )
    process_stat_var.set(pstat)  # TODO check if global var is really necessary

    branch_state = deepcopy(initial_state)
    dblogstep = _make_branch_dblogstep(process_id, fork_step_id, branch_index, user, seed_state=seed_state)
    try:
        _exec_steps(branch, Success(branch_state), dblogstep)
    except Exception as e:
        logger.error("Celery branch execution failed", branch_index=branch_index, error=str(e))

    with transactional(db, logger):
        completed, total = _atomic_increment_completed(fork_step_id)
        is_last_branch = total is not None and completed >= total

        logger.info(
            "Branch completed",
            branch_index=branch_index,
            completed=completed,
            total=total,
            parallel_group=parallel_group_name,
        )

        if is_last_branch:
            _resolve_fork_step(process_id=process_id, fork_step_id=fork_step_id, initial_state=initial_state)

    # The commit above is the hand-off point, so the process is only resumed after it.
    if is_last_branch:
        _resume(process_id, user)


def _resolve_fork_step(
    *,
    process_id: UUID,
    fork_step_id: UUID,
    initial_state: dict,
) -> None:
    """Called by the last-finishing branch to resolve the parallel block in the DB.

    The fork row IS the main-log entry for the parallel step (see ``_main_log_steps``),
    so resolving the parallel block means updating only that row. For failures, propagate
    the worst branch's error state so it's visible on the main log; for successes, keep
    the pre-parallel state.

    Does not commit and does not resume: the caller commits the fork update together
    with the branch increment, and resumes the parent workflow afterwards.

    Raises:
        ValueError: If the fork step does not exist. Resolving nothing would resume the process with the parallel
            step still unresolved.
    """
    fork_step = db.session.get(ProcessStepTable, fork_step_id)
    if fork_step is None:
        # The counter update matches no row, so in practice this does not happen; keep the check as a guard.
        logger.error(
            "Fork step not found while resolving parallel branches",
            process_id=str(process_id),
            fork_step_id=str(fork_step_id),
        )
        raise ValueError(f"Fork step {fork_step_id} not found")

    branch_data = _collect_branch_results(fork_step_id)

    results = [_STATUSES.get(StepStatus(status), Success)(state) for _branch_idx, state, status in branch_data]
    worst = _worst_status(results)

    resolved_status = worst.status if worst else StepStatus.SUCCESS
    resolved_state = worst.unwrap() if worst else initial_state

    fork_step.status = resolved_status
    fork_step.state = resolved_state


def _resume(process_id: UUID, user: str) -> None:
    """Hand the parent workflow over to the RESUME executor, committed by the caller before this.

    The caller commits the fork update separately and does not rely on the transaction
    the RESUME executor opens. That transaction rolls back when resuming fails (for
    example with "incorrect status to resume"), which would also roll back the fork
    update. The fork row would then stay ``waiting``: ``_recoverwf`` treats the parallel
    step as not done and ``_create_fork_step`` only inherits branches from *failed*
    forks, so a manual resume would run every branch again.
    """
    from orchestrator.core.services.executors.types import ExecutorFunction
    from orchestrator.core.services.processes import _get_process, get_execution_context

    process = _get_process(process_id)
    resume_func = get_execution_context()[ExecutorFunction.RESUME]
    resume_func(process, user=user)
