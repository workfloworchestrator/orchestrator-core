# Copyright 2019-2020 SURF.
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


from datetime import timedelta

from orchestrator.db import ProcessTable, db
from orchestrator.targets import Target
from orchestrator.types import State
from orchestrator.utils.datetime import nowtz
from orchestrator.workflow import ProcessStatus, StepList, done, init, step, workflow


@step("Clean up tasks older than one week")
def remove_tasks() -> State:
    delta = timedelta(days=3)
    now = nowtz()
    three_days_ago = now - delta
    tasks = (
        ProcessTable.query.filter(ProcessTable.is_task.is_(True))
        .filter(ProcessTable.last_status == ProcessStatus.COMPLETED)
        .filter(ProcessTable.last_modified_at <= three_days_ago)
        .all()
    )
    count = 0
    for task in tasks:
        db.session.delete(task)
        count += 1

    return {"tasks_removed": count}


@workflow("Clean up old tasks", target=Target.SYSTEM)
def task_clean_up_tasks() -> StepList:
    return init >> remove_tasks >> done
