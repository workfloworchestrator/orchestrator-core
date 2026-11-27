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

"""In-process execution of parallel branches on a thread pool."""

from __future__ import annotations

import functools
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextvars import copy_context
from copy import deepcopy
from typing import cast
from uuid import UUID

import structlog
from sqlalchemy.pool import QueuePool

from orchestrator.core.beta.parallel.branching import (
    _collect_branch_results,
    _make_branch_dblogstep,
    _succeeded_branch_indices,
    _update_fork_step,
    _worst_status,
)
from orchestrator.core.db import db
from orchestrator.core.db.database import ENGINE_ARGUMENTS
from orchestrator.core.settings import app_settings
from orchestrator.core.utils.datetime import nowtz
from orchestrator.core.utils.errors import error_state_to_dict
from orchestrator.core.workflow import (
    Failed,
    Process,
    StepList,
    StepLogFuncInternal,
    StepStatus,
    Success,
    _exec_steps,
)
from pydantic_forms.types import State

logger = structlog.get_logger(__name__)


# Fixed share of the synchronous database connection pool of `db.engine` reserved for HTTP requests, the scheduler and
# other non-fork users.
_NON_FORK_POOL_RESERVE_FRACTION = 4


@functools.lru_cache(maxsize=None)
def _warn_about_default_concurrency_budget(capacity: int, max_workers: int, requested: int, budget: int) -> None:
    logger.warning(
        "Reducing parallel branch concurrency to the connection-pool budget",
        requested_concurrency=requested,
        branch_budget=budget,
        connection_pool_capacity=capacity,
        max_workers=max_workers,
    )


def _check_max_concurrency(value: int | None) -> None:
    if value is not None and value <= 0:
        raise ValueError("max_concurrency must be greater than 0")


def _max_parallel_workers(pending: int, max_concurrency: int | None) -> int:
    """Bound one fork's branch threads by the synchronous database connection pool of ``db.engine``."""
    _check_max_concurrency(max_concurrency)

    pool = db.engine.pool
    pool_size = pool.size() if isinstance(pool, QueuePool) else cast(int, ENGINE_ARGUMENTS["pool_size"])
    max_overflow = getattr(pool, "_max_overflow", cast(int, ENGINE_ARGUMENTS.get("max_overflow", 0)))
    max_workers = app_settings.MAX_WORKERS

    capacity = pool_size + max_overflow
    non_fork_reserve = max(4, capacity // _NON_FORK_POOL_RESERVE_FRACTION)
    # One process-level quarter (at least four connections) is excluded from all fork budgets for HTTP/scheduler;
    # subtract one parent connection per fork.
    # Fork create/update database scopes do not overlap running branches, so they only imply extra slack.
    # The floor allows serial execution for very high MAX_WORKERS or a small synchronous database connection pool; a
    # warning makes that explicit.
    branch_budget = max(1, (capacity - non_fork_reserve) // max_workers - 1)
    requested = max_concurrency if max_concurrency is not None else max_workers
    if min(pending, requested) > branch_budget:
        if max_concurrency is None:
            _warn_about_default_concurrency_budget(capacity, max_workers, requested, branch_budget)
        else:
            logger.warning(
                "Reducing parallel branch concurrency to the connection-pool budget",
                requested_concurrency=requested,
                branch_budget=branch_budget,
                connection_pool_capacity=capacity,
                max_workers=max_workers,
            )
    return min(pending, requested, branch_budget)


def _run_branch(
    branch: StepList,
    initial_state: State,
    *,
    process_id: UUID | None = None,
    parent_step_id: UUID | None = None,
    branch_index: int = 0,
    current_user: str = "",
    state_seed: State | None = None,
) -> Process:
    """Execute a single parallel branch in its own database scope.

    Args:
        branch: The step list to execute.
        initial_state: The base state to deep-copy for this branch.
        process_id: Process ID for DB logging (None = no DB logging).
        parent_step_id: Fork step ID to link child steps to.
        branch_index: Index of this branch (0-based).
        current_user: User who started the workflow.
        state_seed: Optional per-branch state overrides (used by map_parallel).
    """
    with db.database_scope():
        branch_state = deepcopy(initial_state)
        if state_seed is not None:
            branch_state.update(state_seed)

        branch_logstep: StepLogFuncInternal = (
            _make_branch_dblogstep(process_id, parent_step_id, branch_index, current_user, seed_state=state_seed)
            if process_id is not None and parent_step_id is not None
            else lambda step_, p: p  # noqa: E731
        )

        return _exec_steps(branch, Success(branch_state), branch_logstep)


def _run_threadpool_branches(
    branches: list[StepList],
    initial_state: State,
    name: str,
    process_id: UUID | None,
    fork_step_id: UUID | None,
    current_user: str,
    max_concurrency: int | None = None,
    seeds: list[State] | None = None,
) -> Process:
    """Execute branches in a thread pool and collect results synchronously.

    On retry, branches that already succeeded on a prior attempt (recorded under the
    same fork via ``ProcessStepRelationTable``) are skipped. The aggregate result is
    computed from each branch's *latest* attempt in the DB so successful prior
    branches contribute alongside the freshly-executed pending ones.
    """
    n_branches = len(seeds) if seeds else len(branches)

    already_succeeded = _succeeded_branch_indices(fork_step_id) if fork_step_id is not None else set()
    pending = [idx for idx in range(n_branches) if idx not in already_succeeded]

    branch_results: list[Process | None] = [None] * n_branches

    if pending:
        workers = _max_parallel_workers(len(pending), max_concurrency)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    copy_context().run,
                    _run_branch,
                    branches[idx] if len(branches) > 1 else branches[0],
                    initial_state,
                    process_id=process_id,
                    parent_step_id=fork_step_id,
                    branch_index=idx,
                    current_user=current_user,
                    state_seed=seeds[idx] if seeds else None,
                ): idx
                for idx in pending
            }

            def _collect_result(future: Future[Process]) -> None:
                idx = futures[future]
                try:
                    branch_results[idx] = future.result()
                except Exception as e:
                    logger.error("Parallel branch exception", branch_idx=idx, parallel_group=name)
                    branch_results[idx] = Failed(error_state_to_dict(e))

            for future in as_completed(futures):
                _collect_result(future)

    parallel_start_time = nowtz().timestamp()

    # Aggregate from the DB so previously-succeeded branches contribute to the worst-status
    # calculation alongside the branches that just ran in this attempt.
    if fork_step_id is not None:
        results = list(_collect_branch_results(fork_step_id).values())
    else:
        results = [r for r in branch_results if r is not None]

    worst = _worst_status(results)

    if fork_step_id is not None:
        fork_status = worst.status if worst is not None else StepStatus.SUCCESS
        _update_fork_step(fork_step_id, fork_status, initial_state, n_branches)

    # Tell safe_logstep to update the fork row in-place rather than write a
    # separate main-log row (which would collide with the fork by name).
    if worst is not None:
        return worst.__class__(worst.unwrap() | {"__replace_last_state": True})

    return Success(initial_state | {"__replace_last_state": True, "__last_step_started_at": parallel_start_time})
