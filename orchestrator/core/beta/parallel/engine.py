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

"""Executor selection for parallel branches.

Creates the fork step and dispatches the branches to the thread pool (default) or to Celery workers, based on the
``EXECUTOR`` setting.
"""

from __future__ import annotations

from orchestrator.core.beta.parallel.branching import _create_fork_step
from orchestrator.core.beta.parallel.threadpool import _run_threadpool_branches
from orchestrator.core.beta.parallel.worker import _dispatch_worker_branches
from orchestrator.core.settings import ExecutorType, app_settings
from orchestrator.core.workflow import (
    BranchSpec,
    Process,
    _assert_parallel_step_is_visible,
    process_stat_var,
)
from pydantic_forms.types import State


def _exec_parallel_branches(
    branching: BranchSpec,
    initial_state: State,
    max_concurrency: int | None = None,
    seeds: list[State] | None = None,
) -> Process:
    """Execute the branches of ``branching``, dispatching to worker or threadpool based on EXECUTOR setting."""
    pstat = process_stat_var.get(None)
    process_id = pstat.process_id if pstat else None
    current_user = pstat.current_user if pstat else ""
    # A template kind runs its one list per seed; the other kinds have one list per branch.
    branches = list(branching.branches)
    n_branches = len(seeds) if seeds else len(branches)

    # Refuse to run a parallel step that the workflow's step tree walk cannot see. See
    # _assert_parallel_step_is_visible for why that matters.
    if pstat is not None:
        _assert_parallel_step_is_visible(pstat.workflow.steps, branching)

    fork_step_id = (
        _create_fork_step(process_id, branching.name, initial_state, n_branches, current_user, branching.kind)
        if process_id
        else None
    )

    match app_settings.EXECUTOR:
        case ExecutorType.WORKER if process_id is not None and fork_step_id is not None:
            from orchestrator.core.services.workflows import get_workflow_by_name

            wf_table = get_workflow_by_name(pstat.workflow.name) if pstat else None
            is_task = wf_table.is_task if wf_table else False
            return _dispatch_worker_branches(
                branches, initial_state, process_id, current_user, fork_step_id, is_task, seeds=seeds
            )

        case _:
            return _run_threadpool_branches(
                branches,
                initial_state,
                branching.name,
                process_id,
                fork_step_id,
                current_user,
                max_concurrency=max_concurrency,
                seeds=seeds,
            )
