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
from collections.abc import Callable
from http import HTTPStatus
from typing import Any
from uuid import UUID

import structlog
from celery.result import AsyncResult
from kombu.exceptions import ConnectionError, OperationalError
from sqlalchemy import select

from orchestrator import app_settings
from orchestrator.api.error_handling import raise_status
from orchestrator.db import ProcessTable, db
from orchestrator.services.processes import (
    SYSTEM_USER,
    can_be_resumed,
    create_process,
    delete_process,
    set_process_status,
)
from orchestrator.services.workflows import get_workflow_by_name
from orchestrator.workflow import ProcessStat, ProcessStatus
from pydantic_forms.types import State

logger = structlog.get_logger(__name__)


def _block_when_testing(task_result: AsyncResult) -> None:
    # Enables "Sync celery tasks. This will let the app wait until celery completes"
    if app_settings.TESTING:
        process_id = task_result.get()
        if not process_id:
            raise RuntimeError("Celery worker has failed to resume process")


def _celery_start_process(pstat: ProcessStat, user: str = SYSTEM_USER, **kwargs: Any) -> UUID:
    """Client side call of Celery."""
    from orchestrator.services.tasks import NEW_TASK, NEW_WORKFLOW, get_celery_task

    if not (wf_table := get_workflow_by_name(pstat.workflow.name)):
        raise_status(HTTPStatus.NOT_FOUND, "Workflow in Database does not exist")

    task_name = NEW_TASK if wf_table.is_task else NEW_WORKFLOW
    trigger_task = get_celery_task(task_name)
    try:
        result = trigger_task.delay(pstat.process_id, user)
        _block_when_testing(result)
        return pstat.process_id
    except (ConnectionError, OperationalError) as e:
        # If connection to Redis fails and process can't be started, we need to remove the created process
        logger.warning("Connection error when submitting task to Celery. Delete newly created process from database.")
        delete_process(pstat.process_id)
        raise e


def _celery_resume_process(
    process: ProcessTable,
    *,
    user: str | None = None,
    **kwargs: Any,
) -> bool:
    """Client side call of Celery."""
    from orchestrator.services.tasks import RESUME_TASK, RESUME_WORKFLOW, get_celery_task

    last_process_status = process.last_status

    task_name = RESUME_TASK if process.workflow.is_task else RESUME_WORKFLOW
    trigger_task = get_celery_task(task_name)

    _celery_set_process_status_resumed(process.process_id)

    try:
        result = trigger_task.delay(process.process_id, user)
        _block_when_testing(result)

        return process.process_id
    except (ConnectionError, OperationalError) as e:
        logger.warning(
            "Connection error when submitting task to celery. Resetting process status back",
            current_status=process.last_status,
            last_status=last_process_status,
        )
        set_process_status(process.process_id, last_process_status)
        raise e


def _celery_set_process_status_resumed(process_id: UUID) -> None:
    """Set the process status to RESUMED to show its waiting to be picked up by a worker.

    uses with_for_update to lock the subscription in a transaction, preventing other changes.
    rolls back transation and raises an exception when it can't change to RESUMED to prevent it from being added to the queue.

    Args:
        process_id: Process ID to fetch process from DB
    """
    stmt = select(ProcessTable).where(ProcessTable.process_id == process_id).with_for_update()

    result = db.session.execute(stmt)
    locked_process = result.scalar_one_or_none()

    if not locked_process:
        raise ValueError(f"Process not found: {process_id}")

    if can_be_resumed(locked_process.last_status):
        locked_process.last_status = ProcessStatus.RESUMED
        db.session.commit()
    else:
        db.session.rollback()
        raise ValueError(f"Process has incorrect status to resume: {locked_process.last_status}")


def _celery_validate(validation_workflow: str, json: list[State] | None) -> None:
    pstat = create_process(validation_workflow, user_inputs=json)
    _celery_start_process(pstat)


CELERY_EXECUTION_CONTEXT: dict[str, Callable] = {
    "start": _celery_start_process,
    "resume": _celery_resume_process,
    "validate": _celery_validate,
}
