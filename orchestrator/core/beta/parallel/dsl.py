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

"""The public DSL for parallel steps: :func:`parallel` and :func:`map_parallel`.

The step function that each one builds keeps its execution options (``max_concurrency`` and the ``map_parallel`` items
key) and delegates the fan-out itself to :mod:`orchestrator.core.beta.parallel.engine`.
"""

from __future__ import annotations

import structlog

from orchestrator.core.beta.parallel.engine import _exec_parallel_branches
from orchestrator.core.beta.parallel.threadpool import _check_max_concurrency
from orchestrator.core.db import db
from orchestrator.core.db.database import transactional
from orchestrator.core.utils.auth import Authorizer
from orchestrator.core.workflow import (
    BranchKind,
    BranchSpec,
    Process,
    Step,
    StepList,
    Success,
    begin,
    make_step_function,
)
from pydantic_forms.types import State

logger = structlog.get_logger(__name__)


def _make_parallel_step(
    name: str,
    branches: list[StepList],
    retry_auth_callback: Authorizer | None = None,
    max_concurrency: int | None = None,
) -> Step:
    """Create a parallel step from a list of branches (internal implementation)."""
    _check_max_concurrency(max_concurrency)
    if len(branches) < 2:
        raise ValueError("parallel() requires at least 2 branches")

    # Validate no inputsteps or callback steps in branches
    def _validate_branch_step(branch_idx: int, s: Step) -> bool:
        if s.form is not None:
            raise ValueError(
                f"Parallel branches must not contain inputsteps. Found inputstep '{s.name}' in branch {branch_idx}."
            )
        if s.is_callback_step:
            raise ValueError(
                f"Parallel branches must not contain callback steps. "
                f"Found callback_step '{s.name}' in branch {branch_idx}."
            )
        return False

    any(_validate_branch_step(idx, s) for idx, branch in enumerate(branches) for s in branch)

    branching = BranchSpec(name, BranchKind.PARALLEL, tuple(branches))

    def func(initial_state: State) -> Process:
        with transactional(db, logger):
            return _exec_parallel_branches(branching, initial_state, max_concurrency=max_concurrency)

    return make_step_function(func, name, retry_auth_callback=retry_auth_callback, branching=branching)


def parallel(
    name: str,
    *branches: StepList | Step,
    retry_auth_callback: Authorizer | None = None,
    max_concurrency: int | None = None,
) -> Step:
    """Execute multiple step sequences in parallel.

    Each branch receives a deep copy of the current state. Branch results are
    persisted individually in the DB (via ``ProcessStepRelationTable``) and are
    **not** merged back into the main workflow state. The step after the parallel
    block receives the pre-parallel state. Branch data can be accessed from the DB
    via ``fork_step.child_steps``.

    Args:
        name: Name of the parallel step. It is the step's only identifier within the workflow at runtime: it names
            the fork step row, a worker uses it to look up the step and rebuild a branch, and a retry uses it to find
            the earlier failed fork to inherit successful branches from. It must therefore be unique within the
            workflow, including in nested branches, step groups and ``map_parallel`` templates; ``make_workflow``
            raises ``ValueError`` on a duplicate name.
        *branches: multiple Step or StepList to execute concurrently
        retry_auth_callback: Authorization callback for retrying on failure
        max_concurrency: Maximum concurrent branch threads. Defaults to ``MAX_WORKERS`` and, together with
            explicit values, is capped by the synchronous database connection pool budget. Ignored with
            ``EXECUTOR=worker``; worker concurrency controls execution there.

    Returns:
        A Step that can be composed with >> operator

    Raises:
        ValueError: If fewer than 2 branches provided
        ValueError: If any branch contains an inputstep
        ValueError: If ``max_concurrency`` is not positive
    """
    branch_steplists = [begin >> branch for branch in branches]
    return _make_parallel_step(
        name, list(branch_steplists), retry_auth_callback=retry_auth_callback, max_concurrency=max_concurrency
    )


def map_parallel(
    name: str,
    items_key: str,
    branch: StepList | Step,
    max_concurrency: int | None = None,
) -> Step:
    """Map the Step or StepList to all items in ``state[items_key]``.

    At runtime the step reads ``state[items_key]`` and schedules one branch per item.
    Each branch runs a deep copy of *branch* with the item merged into its initial state:

    - **Dict items** are merged directly: ``initial_state | item``.
      The item's keys become available as ordinary step arguments in that branch.
    - **Non-dict items** are injected under ``{"item": <value>, "item_index": <int>}``.

    Branch results are persisted individually in the DB (via ``ProcessStepRelationTable``)
    and are **not** merged back into the main workflow state. The step after the foreach
    block receives the pre-parallel state. Branch data can be accessed from the DB
    via ``fork_step.child_steps``.

    Example::

        @step("Fetch ports")
        def fetch_ports():
            return {"ports": [{"port_id": "p1", "vlan": 100},
                               {"port_id": "p2", "vlan": 200}]}

        @step("Provision port")
        def provision_port(port_id, vlan):
            result = call_provisioning_api(port_id, vlan)
            return {f"port_{port_id}_result": result}

        @workflow("Provision dual port", target=Target.CREATE)
        def provision_dual():
            return (
                init
                >> fetch_ports
                >> map_parallel("Provision ports", "ports", provision_port)
                >> link_ports
                >> done
            )

    Example of a multi-step ``StepList``::

        @step("Reserve port")
        def reserve_port(port_id, vlan):
            return call_reservation_api(port_id, vlan)

        map_parallel(
            "Provision ports",
            "ports",
            begin >> reserve_port >> provision_port,
        )

    Args:
        name: Name of the parallel step. It is the step's only identifier within the workflow at runtime: it names
            the fork step row, a worker uses it to look up the step and rebuild a branch, and a retry uses it to find
            the earlier failed fork to inherit successful branches from. It must therefore be unique within the
            workflow, including in nested branches, step groups and ``map_parallel`` templates; ``make_workflow``
            raises ``ValueError`` on a duplicate.
        items_key: Key in the workflow state whose value is the list to iterate over.
        branch: Step or StepList executed once per item, with the item merged into state.
        max_concurrency: Maximum concurrent item branches. Defaults to ``MAX_WORKERS`` and, together with
            explicit values, is capped by the synchronous database connection pool budget. Ignored with
            ``EXECUTOR=worker``; worker concurrency controls execution there.

    Returns:
        A Step that can be composed with the ``>>`` operator.

    Raises:
        ValueError: If ``state[items_key]`` is not iterable at runtime.
        ValueError: If ``max_concurrency`` is not positive.
    """
    _check_max_concurrency(max_concurrency)
    branch_steplist = begin >> branch
    branching = BranchSpec(name, BranchKind.MAP_PARALLEL, (branch_steplist,))

    def func(initial_state: State) -> Process:
        with transactional(db, logger):
            raw = initial_state.get(items_key)
            if raw is None:
                raise ValueError(f"map_parallel: key '{items_key}' not found in state")
            items = list(raw)

            if not items:
                return Success(initial_state)

            # Build per-item seeds — dict items are used as-is; scalars get a wrapper.
            seeds: list[State] = [
                item if isinstance(item, dict) else {"item": item, "item_index": idx} for idx, item in enumerate(items)
            ]

            return _exec_parallel_branches(branching, initial_state, max_concurrency=max_concurrency, seeds=seeds)

    return make_step_function(func, name, branching=branching)
