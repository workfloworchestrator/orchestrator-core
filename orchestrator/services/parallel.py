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

"""Parallel branch execution support for distributed workers.

Handles:
- Executing a single branch in a worker task
- Atomic join counter (UPDATE...RETURNING)
- Last-finisher detection and parent workflow resumption
"""
from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from uuid import UUID

import structlog
from more_itertools import unique_everseen
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload

from orchestrator.db import ProcessStepTable, ProcessTable, db
from orchestrator.db.models import ProcessStepRelationTable
from orchestrator.workflow import (
    _STATUSES,
    ProcessStat,
    Step,
    StepList,
    StepStatus,
    Success,
    Workflow,
    _exec_steps,
    _make_branch_dblogstep,
    _worst_status,
    process_stat_var,
    reconstruct_branch,
)

logger = structlog.get_logger(__name__)


def _atomic_increment_completed(fork_step_id: UUID) -> tuple[int, int | None]:
    """Atomically increment parallel_completed_count and return (new_count, total_branches).

    Uses UPDATE...RETURNING for atomic last-finisher detection, avoiding an extra SELECT.
    """
    stmt = (
        update(ProcessStepTable)
        .where(ProcessStepTable.step_id == fork_step_id)
        .values(parallel_completed_count=ProcessStepTable.parallel_completed_count + 1)
        .returning(ProcessStepTable.parallel_completed_count, ProcessStepTable.parallel_total_branches)
    )
    result = db.session.execute(stmt)
    completed, total = result.one()
    db.session.commit()
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

    first_per_branch = unique_everseen(relations, key=lambda r: r.branch_index)
    return [(rel.branch_index, rel.child_step.state, rel.child_step.status) for rel in first_per_branch]


def _child_step_lists(s: Step) -> Iterator[StepList]:
    """Yield the nested step lists (branches and templates) attached to a step."""
    yield from getattr(s, "_parallel_branches", [])
    template = getattr(s, "_foreach_branch_template", None)
    if template is not None:
        yield template


def _find_parallel_step(steps: StepList, group_name: str) -> Step | None:
    """Recursively search steps (and their parallel branches) for a parallel group name.

    Walks the step tree depth-first, checking each step's ``_parallel_group_name``
    attribute. Also recurses into ``_parallel_branches`` (static parallel) and
    ``_foreach_branch_template`` (foreach_parallel).

    Args:
        steps: A StepList (iterable of Step functions) to search.
        group_name: The parallel group name to find.

    Returns:
        The Step with matching ``_parallel_group_name``, or None if not found.
    """
    for s in steps:
        if getattr(s, "_parallel_group_name", None) == group_name:
            return s
        found = next(
            (
                result
                for child in _child_step_lists(s)
                if (result := _find_parallel_step(child, group_name)) is not None
            ),
            None,
        )
        if found is not None:
            return found
    return None


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
    from orchestrator.workflows import get_workflow

    fork_step = db.session.get(ProcessStepTable, fork_step_id)
    if fork_step is None:
        raise ValueError(f"Fork step {fork_step_id} not found")

    parallel_group_name = fork_step.name

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
    results and resumes the parent workflow.
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
    process_stat_var.set(pstat)

    branch_state = deepcopy(initial_state)
    dblogstep = _make_branch_dblogstep(process_id, fork_step_id, branch_index, user, seed_state=seed_state)
    try:
        _exec_steps(branch, Success(branch_state), dblogstep)
    except Exception as e:
        logger.error("Celery branch execution failed", branch_index=branch_index, error=str(e))

    completed, total = _atomic_increment_completed(fork_step_id)

    logger.info(
        "Branch completed",
        branch_index=branch_index,
        completed=completed,
        total=total,
        parallel_group=parallel_group_name,
    )

    if total is not None and completed >= total:
        _join_and_resume(
            process_id=process_id,
            fork_step_id=fork_step_id,
            initial_state=initial_state,
            user=user,
        )


def _join_and_resume(
    *,
    process_id: UUID,
    fork_step_id: UUID,
    initial_state: dict,
    user: str,
) -> None:
    """Called by the last-finishing branch to determine status and resume the parent workflow."""
    branch_data = _collect_branch_results(fork_step_id)

    # Reconstruct Process objects from DB state + status
    results = [_STATUSES.get(StepStatus(status), Success)(state) for _branch_idx, state, status in branch_data]
    worst = _worst_status(results)

    fork_step = db.session.get(ProcessStepTable, fork_step_id)
    if fork_step is not None:
        fork_step.status = worst.status if worst is not None else StepStatus.SUCCESS
        fork_step.state = initial_state
        db.session.commit()

    # Resume the parent workflow via the configured executor
    from orchestrator.services.processes import _get_process, get_execution_context

    process = _get_process(process_id)
    resume_func = get_execution_context()["resume"]
    resume_func(process, user=user)
