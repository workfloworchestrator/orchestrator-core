# Copyright 2019-2026 SURF.
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

from orchestrator.db import ProcessTable, db
from orchestrator.workflow import PredicateContext, RunPredicateFail, RunPredicatePass, RunPredicateResult


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
            ProcessTable.last_status != "completed",
        )
    )
    if uncompleted_count == 0:
        return RunPredicatePass()
    return RunPredicateFail(f"Workflow '{workflow_name}' already has {uncompleted_count} uncompleted instance(s)")
