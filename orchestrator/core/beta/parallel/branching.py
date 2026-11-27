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

"""Branch execution support shared by every executor.

Handles the fork step a branching step creates, the per-branch step log, the relations between the fork and its branch
steps, and the result of each branch. The executors in :mod:`orchestrator.core.beta.parallel.threadpool` and
:mod:`orchestrator.core.beta.parallel.worker` build on this.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Sequence
from uuid import UUID

import structlog
from more_itertools import unique_everseen
from sqlalchemy import func, select, update
from sqlalchemy.orm import joinedload

from orchestrator.core.db import ProcessStepTable, db
from orchestrator.core.db.models import ProcessStepRelationTable
from orchestrator.core.utils.datetime import nowtz
from orchestrator.core.workflow import (
    _STATUSES,
    BranchKind,
    Process,
    Step,
    StepList,
    StepLogFuncInternal,
    StepStatus,
    Success,
)
from pydantic_forms.types import State

logger = structlog.get_logger(__name__)

_STATUS_PRIORITY: list[str] = ["isfailed", "iswaiting", "issuspend", "isawaitingcallback"]


def _worst_status(branch_results: list[Process]) -> Process | None:
    """Return the branch with the worst non-success status, or None if all succeeded."""
    return next(
        (result for check in _STATUS_PRIORITY for result in branch_results if getattr(result, check)()),
        None,
    )


def branch_step_name(branch_index: int, step_name: str) -> str:
    """Return the name of a branch step's row in the process log.

    Args:
        branch_index: Index of the branch the step belongs to.
        step_name: Name of the step itself.

    Returns:
        The step name prefixed with the branch, for example ``"[Branch 0] Provision"``.
    """
    return f"[Branch {branch_index}] {step_name}"


def reconstruct_branch(parallel_step: Step, branch_index: int) -> StepList:
    """Return the step list to run for ``branch_index`` of ``parallel_step``, for a Celery worker.

    Args:
        parallel_step: A step created by :func:`orchestrator.core.beta.parallel.dsl.parallel` or
            :func:`orchestrator.core.beta.parallel.dsl.map_parallel`.
        branch_index: Zero-based index of the branch to reconstruct.

    Raises:
        ValueError: If ``parallel_step`` doesn't fan out, so it has no branch to reconstruct.
        IndexError: If ``branch_index`` is out of range (static parallel only).
    """
    if parallel_step.branching is None:
        raise ValueError(f"Step '{parallel_step.name}' is not a parallel step")
    return parallel_step.branching.reconstruct_branch(branch_index)


def _make_branch_dblogstep(
    process_id: UUID,
    parent_step_id: UUID,
    branch_index: int,
    current_user: str,
    seed_state: State | None = None,
) -> StepLogFuncInternal:
    """Create a step logger for a parallel branch that writes its own ProcessStepTable rows.

    Each branch step is persisted individually and linked to the parent fork step
    via ProcessStepRelationTable. The seed_state is stored on the first relation
    so the join can strip seed keys from branch results.

    Starts the per-branch ``order_id`` counter above any existing order_ids for this
    (fork, branch_index) so retry attempts are sortable as "latest" by
    ``_collect_branch_results`` (which picks the row with the highest order_id per
    branch_index).
    """
    existing_max = db.session.scalars(
        select(func.max(ProcessStepRelationTable.order_id)).where(
            ProcessStepRelationTable.parent_step_id == parent_step_id,
            ProcessStepRelationTable.branch_index == branch_index,
        )
    ).first()
    order_counter = itertools.count(existing_max + 1 if existing_max is not None else 0)

    def branch_dblogstep(step_: Step, p: Process) -> Process:
        step_state = p.unwrap()
        step_name = step_state.pop("__step_name_override", step_.name)

        child_step = ProcessStepTable(
            process_id=process_id,
            name=branch_step_name(branch_index, step_name),
            status=p.status,
            state=step_state,
            created_by=current_user,
        )
        db.session.add(child_step)
        db.session.flush()

        order_id = next(order_counter)
        relation = ProcessStepRelationTable(
            parent_step_id=parent_step_id,
            child_step_id=child_step.step_id,
            order_id=order_id,
            branch_index=branch_index,
            seed_state=seed_state if order_id == 0 else None,
        )
        db.session.add(relation)
        db.session.commit()
        return p.__class__(child_step.state)

    return branch_dblogstep


def _select_branch_relations(fork_step_id: UUID) -> Sequence[ProcessStepRelationTable]:
    """Return the relations of ``fork_step_id``, latest step first within each branch.

    The ``child_step`` is eagerly loaded because it is ``lazy="raise"``; callers read its status and state. One query
    serves both the latest result per branch and the relations to inherit on a retry.
    """
    stmt = (
        select(ProcessStepRelationTable)
        .where(ProcessStepRelationTable.parent_step_id == fork_step_id)
        .options(joinedload(ProcessStepRelationTable.child_step))
        .order_by(ProcessStepRelationTable.branch_index, ProcessStepRelationTable.order_id.desc())
    )
    return db.session.execute(stmt).scalars().all()


def _latest_branch_results(relations: Iterable[ProcessStepRelationTable]) -> dict[int, Process]:
    """Convert relations ordered latest-first into the latest result per branch index.

    Takes the first step per branch (the highest ``order_id``) as the branch result and converts its status back into
    the matching ``Process``, so callers can compare results without converting themselves.
    """
    return {
        rel.branch_index: _STATUSES.get(StepStatus(rel.child_step.status), Success)(rel.child_step.state)
        for rel in unique_everseen(relations, key=lambda rel: rel.branch_index)
    }


def _collect_branch_results(fork_step_id: UUID) -> dict[int, Process]:
    """Collect the latest branch result per branch index from DB via ProcessStepRelationTable."""
    return _latest_branch_results(_select_branch_relations(fork_step_id))


def _succeeded_branch_indices(fork_step_id: UUID) -> set[int]:
    """Return the set of branch indices whose most recent attempt succeeded.

    Used by retry logic to skip branches that already completed successfully
    on a previous attempt of the same parallel group.
    """
    return {idx for idx, result in _collect_branch_results(fork_step_id).items() if result.issuccess()}


def _create_fork_step(
    process_id: UUID,
    name: str,
    initial_state: State,
    total_branches: int,
    current_user: str,
    branch_kind: BranchKind,
) -> UUID:
    """Create a new fork step for this (process, branch group).

    Always inserts a fresh fork row — mirrors orchestrator-core's existing retry
    pattern where each new attempt of a step gets its own row, leaving prior
    failed rows untouched as history. When a prior *failed* fork for the same
    parallel group exists, its successful branch relations are inherited by the
    new fork so ``fork.child_steps`` and the atomic join logic see the full set
    of resolved branches; the failed/pending branches are re-dispatched.

    Uses a separate ``database_scope()`` session so the change is committed
    independently of the caller's transaction. This ensures the fork step is
    visible to branch threads that run on their own connections from the
    synchronous database connection pool of ``db.engine``.

    Returns the fork step_id (not the ORM object) to avoid stale-object issues.
    """
    with db.database_scope():
        prior_failed = db.session.scalars(
            select(ProcessStepTable)
            .where(
                ProcessStepTable.process_id == process_id,
                ProcessStepTable.name == name,
                ProcessStepTable.branch_kind == branch_kind,
                ProcessStepTable.status == StepStatus.FAILED,
            )
            .order_by(ProcessStepTable.completed_at.desc())
            .limit(1)
        ).first()

        inherited_relations: list[ProcessStepRelationTable] = []
        succeeded_branches: set[int] = set()
        if prior_failed is not None:
            # Re-inherit the steps of the branches that succeeded in the prior fork, as they were recorded there: the
            # latest step of each branch determines its result, and the earlier ones are its history. One query reads
            # the relations; each copy keeps its own order_id, which is part of the primary key, so the copy order
            # doesn't matter.
            relations = _select_branch_relations(prior_failed.step_id)
            succeeded_branches = {
                idx for idx, result in _latest_branch_results(relations).items() if result.issuccess()
            }
            inherited_relations = [rel for rel in relations if rel.branch_index in succeeded_branches]

        now = nowtz()
        fork_step = ProcessStepTable(
            process_id=process_id,
            name=name,
            status=StepStatus.SUCCESS,
            state=initial_state,
            created_by=current_user,
            branch_count=total_branches,
            branch_kind=branch_kind,
            branches_completed=len(succeeded_branches),
            started_at=now,
            completed_at=now,
        )
        db.session.add(fork_step)
        db.session.flush()

        db.session.add_all(
            ProcessStepRelationTable(
                parent_step_id=fork_step.step_id,
                child_step_id=rel.child_step_id,
                order_id=rel.order_id,
                branch_index=rel.branch_index,
                seed_state=rel.seed_state,
            )
            for rel in inherited_relations
        )
        db.session.commit()
        return fork_step.step_id


def _update_fork_step(fork_step_id: UUID, status: str, state: State, n_branches: int) -> None:
    """Update the fork step status via direct SQL UPDATE.

    Uses a separate ``database_scope()`` session so the UPDATE is committed
    independently, bypassing ``disable_commit`` on the caller's session.
    """
    with db.database_scope():
        stmt = (
            update(ProcessStepTable)
            .where(ProcessStepTable.step_id == fork_step_id)
            .values(
                status=status,
                state=state,
                branches_completed=n_branches,
            )
        )
        db.session.execute(stmt)
        db.session.commit()
