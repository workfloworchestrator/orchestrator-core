# Copyright 2019-2020 SURF, GÉANT.
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

import structlog
from sqlalchemy import select

from orchestrator.db import ProcessTable, db
from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.types import EntityType
from orchestrator.settings import app_settings, get_authorizers
from orchestrator.targets import Target
from orchestrator.utils.datetime import nowtz
from orchestrator.workflow import ProcessStatus, StepList, done, init, step, workflow
from pydantic_forms.types import State

authorizers = get_authorizers()
logger = structlog.get_logger(__name__)


@step("Clean up completed tasks older than TASK_LOG_RETENTION_DAYS")
def remove_tasks() -> State:
    cutoff = nowtz() - timedelta(days=app_settings.TASK_LOG_RETENTION_DAYS)
    tasks = db.session.scalars(
        select(ProcessTable)
        .filter(ProcessTable.is_task.is_(True))
        .filter(ProcessTable.last_status == ProcessStatus.COMPLETED)
        .filter(ProcessTable.last_modified_at <= cutoff)
    )
    count = 0
    deleted_pid_list = []
    for task in tasks:
        db.session.delete(task)
        count += 1
        deleted_pid_list.append(task.process_id)

    return {"tasks_removed": count, "deleted_process_id_list": deleted_pid_list}


@step("Clean up ai_search_indexes")
def cleanup_ai_search_index(deleted_process_id_list: list) -> State:
    """Try catch for now, in version 5 the ai_search_index table will always exist."""
    count = 0
    try:
        if len(deleted_process_id_list) > 0:
            rows_to_delete = db.session.scalars(
                select(AiSearchIndex)
                .filter(AiSearchIndex.entity_type == EntityType.PROCESS)
                .filter(AiSearchIndex.entity_id.in_(deleted_process_id_list))
            )
            for row in rows_to_delete:
                db.session.delete(row)
                count += 1

        return {"ai_search_index_rows_deleted": count}

    except Exception as exc:
        logger.warning("Table ai_search_index does not exist", error=str(exc))
        return {"ai_search_index_rows_deleted": count, "ai_search_table_exists": False}


@workflow(
    "Clean up old tasks",
    target=Target.SYSTEM,
    authorize_callback=authorizers.authorize_callback,
    retry_auth_callback=authorizers.retry_auth_callback,
)
def task_clean_up_tasks() -> StepList:
    return (
        init
        >> remove_tasks
        >> cleanup_ai_search_index
        >> done
    )
