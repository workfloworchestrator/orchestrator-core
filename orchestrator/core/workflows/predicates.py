# Copyright 2019-2026 SURF, GÉANT.
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

from __future__ import annotations

from sqlalchemy import func, select

from orchestrator.core.db import ProcessStepTable, ProcessTable, db
from orchestrator.core.workflow import (
    CALLBACK_TIMEOUT_KEY,
    PredicateContext,
    ProcessStatus,
    RunPredicateFail,
    RunPredicatePass,
    RunPredicateResult,
    StepStatus,
)


def no_uncompleted_instance(context: PredicateContext) -> RunPredicateResult:
    """Predicate that prevents starting if an uncompleted instance of the workflow exists.

    Args:
        context: PredicateContext containing the workflow information.

    Returns:
        RunPredicatePass if no uncompleted instances exist, or RunPredicateFail with reason otherwise.
    """
    workflow_name = context.workflow_key
    uncompleted_count = db.session.scalar(
        select(func.count())
        .select_from(ProcessTable)
        .filter(
            ProcessTable.workflow.has(name=workflow_name),
            ProcessTable.last_status.not_in([ProcessStatus.COMPLETED, ProcessStatus.ABORTED]),
        )
    )
    if uncompleted_count == 0:
        return RunPredicatePass()
    return RunPredicateFail(f"Workflow '{workflow_name}' already has {uncompleted_count} uncompleted instance(s)")


def awaiting_callbacks_exist(context: PredicateContext) -> RunPredicateResult:
    """Predicate that only runs the workflow when a process is awaiting a callback that has a timeout set.

    Composes with :func:`no_uncompleted_instance` so the timeout sweep neither overlaps a previous run nor starts a run
    (and thus creates a process row) when there is nothing to check. The timeout lives in the awaiting step's JSONB
    state, so we join to the awaiting step and require the ``__callback_timeout`` key; callbacks without a timeout (the
    default) never need the sweep. Joining on ``last_status`` excludes the lingering awaiting-callback step rows of
    aborted/failed processes.

    Args:
        context: PredicateContext containing the workflow information.

    Returns:
        RunPredicatePass when work exists and no instance is running, RunPredicateFail otherwise.
    """
    match no_uncompleted_instance(context):
        case RunPredicateFail() as fail:
            return fail
        case _:
            awaiting_count = db.session.scalar(
                select(func.count())
                .select_from(ProcessTable)
                .join(ProcessStepTable, ProcessStepTable.process_id == ProcessTable.process_id)
                .filter(
                    ProcessTable.last_status == ProcessStatus.AWAITING_CALLBACK,
                    ProcessStepTable.status == StepStatus.AWAITING_CALLBACK,
                    ProcessStepTable.state.has_key(CALLBACK_TIMEOUT_KEY),
                )
            )
            if awaiting_count:
                return RunPredicatePass()
            return RunPredicateFail("No processes are awaiting a callback with a timeout")
