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

from collections.abc import Callable

from sqlalchemy import func, select

from orchestrator.db import ProcessTable, db


def no_uncompleted_instance(workflow_name: str) -> Callable[[], bool]:
    """Create a predicate that prevents starting if an uncompleted instance of the given workflow exists.

    Args:
        workflow_name: The workflow name to check for uncompleted instances.

    Returns:
        A callable that returns True if no uncompleted instances exist, False otherwise.
    """

    def predicate() -> bool:
        uncompleted_count = db.session.scalar(
            select(func.count())
            .select_from(ProcessTable)
            .filter(
                ProcessTable.workflow.has(name=workflow_name),
                ProcessTable.last_status != "completed",
            )
        )
        return uncompleted_count == 0

    return predicate
