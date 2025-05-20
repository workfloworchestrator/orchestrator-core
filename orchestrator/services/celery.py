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

from orchestrator import app_settings
from orchestrator.api.error_handling import raise_status
from orchestrator.db import ProcessTable, db
from orchestrator.services.input_state import store_input_state
from orchestrator.services.processes import create_process, delete_process
from orchestrator.services.workflows import get_workflow_by_name
from orchestrator.workflows import get_workflow
from pydantic_forms.types import State

SYSTEM_USER = "SYSTEM"

logger = structlog.get_logger(__name__)


def _block_when_testing(task_result: AsyncResult) -> None:
    # Enables "Sync celery tasks. This will let the app wait until celery completes"
    if app_settings.TESTING:
        process_id = task_result.get()
        if not process_id:
            raise RuntimeError("Celery worker has failed to resume process")


def _celery_start_process(
    workflow_key: str, user_inputs: list[State] | None, user: str = SYSTEM_USER, **kwargs: Any
) -> UUID:
    """Client side call of Celery."""
    from orchestrator.services.tasks import NEW_TASK, NEW_WORKFLOW, get_celery_task

    workflow = get_workflow(workflow_key)
    if not workflow:
        raise_status(HTTPStatus.NOT_FOUND, "Workflow does not exist")

    wf_table = get_workflow_by_name(workflow.name)
    if not wf_table:
        raise_status(HTTPStatus.NOT_FOUND, "Workflow in Database does not exist")

    task_name = NEW_TASK if wf_table.is_task else NEW_WORKFLOW
    trigger_task = get_celery_task(task_name)
    pstat = create_process(workflow_key, user_inputs, user)
    try:
        result = trigger_task.delay(pstat.process_id, workflow_key, user)
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
    user_inputs: list[State] | None = None,
    user: str | None = None,
    **kwargs: Any,
) -> UUID:
    """Client side call of Celery."""
    from orchestrator.services.processes import load_process
    from orchestrator.services.tasks import RESUME_TASK, RESUME_WORKFLOW, get_celery_task

    pstat = load_process(process)
    last_process_status = process.last_status
    workflow = pstat.workflow

    wf_table = get_workflow_by_name(workflow.name)
    if not workflow or not wf_table:
        raise_status(HTTPStatus.NOT_FOUND, "Workflow does not exist")

    task_name = RESUME_TASK if wf_table.is_task else RESUME_WORKFLOW
    trigger_task = get_celery_task(task_name)

    user_inputs = user_inputs or [{}]
    store_input_state(pstat.process_id, user_inputs, "user_input")
    try:
        _celery_set_process_status_resumed(process)
        result = trigger_task.delay(pstat.process_id, user)
        _block_when_testing(result)

        return pstat.process_id
    except (ConnectionError, OperationalError) as e:
        logger.warning(
            "Connection error when submitting task to celery. Resetting process status back",
            current_status=process.last_status,
            last_status=last_process_status,
        )
        _celery_set_process_status(process, last_process_status)
        raise e


def _celery_set_process_status(process: ProcessTable, status: str) -> None:
    process.last_status = status
    db.session.add(process)
    db.session.commit()


def _celery_set_process_status_resumed(process: ProcessTable) -> None:
    """Set the process status to RESUMED to prevent re-adding to task queue.

    Args:
        process: Process from database
    """
    from orchestrator.db import db
    from orchestrator.workflow import ProcessStatus

    process.last_status = ProcessStatus.RESUMED
    db.session.add(process)
    db.session.commit()


def _celery_validate(validation_workflow: str, json: list[State] | None) -> None:
    _celery_start_process(validation_workflow, user_inputs=json)


CELERY_EXECUTION_CONTEXT: dict[str, Callable] = {
    "start": _celery_start_process,
    "resume": _celery_resume_process,
    "validate": _celery_validate,
}
