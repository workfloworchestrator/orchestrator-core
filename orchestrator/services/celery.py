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
from collections.abc import Callable
from http import HTTPStatus
from typing import Any
from uuid import UUID

from orchestrator import app_settings
from orchestrator.api.error_handling import raise_status
from orchestrator.db import ProcessTable
from orchestrator.services.processes import create_process
from orchestrator.targets import Target
from orchestrator.types import State
from orchestrator.workflows import get_workflow

SYSTEM_USER = "SYSTEM"


def _celery_start_process(
    workflow_key: str, user_inputs: list[State] | None, user: str = SYSTEM_USER, **kwargs: Any
) -> UUID:
    """Client side call of Celery."""
    from orchestrator.services.tasks import NEW_TASK, NEW_WORKFLOW, get_celery_task

    workflow = get_workflow(workflow_key)
    if not workflow:
        raise_status(HTTPStatus.NOT_FOUND, "Workflow does not exist")

    task_name = NEW_TASK if workflow.target == Target.SYSTEM else NEW_WORKFLOW
    trigger_task = get_celery_task(task_name)
    pstat = create_process(workflow_key, user_inputs, user)

    tasks = pstat.state.s
    result = trigger_task.delay(pstat.process_id, workflow_key, tasks, user)

    # Enables "Sync celery tasks. This will let the app wait until celery completes"
    if app_settings.TESTING:
        process_id = result.get()
        if not process_id:
            raise RuntimeError("Celery worker has failed to resume process")

    return pstat.process_id


def _celery_resume_process(
    process: ProcessTable,
    *,
    user_inputs: list[State] | None,
    user: str | None,
    **kwargs: Any,
) -> UUID:
    """Client side call of Celery."""
    from orchestrator.services.processes import load_process
    from orchestrator.services.tasks import RESUME_TASK, RESUME_WORKFLOW, get_celery_task

    pstat = load_process(process)
    workflow = pstat.workflow

    task_name = RESUME_TASK if workflow.target == Target.SYSTEM else RESUME_WORKFLOW
    trigger_task = get_celery_task(task_name)
    result = trigger_task.delay(pstat.process_id, user_inputs, user)

    _celery_set_process_status_resumed(process)

    # Enables "Sync celery tasks. This will let the app wait until celery completes"
    if app_settings.TESTING:
        process_id = result.get()
        if not process_id:
            raise RuntimeError("Celery worker has failed to resume process")

    return pstat.process_id


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
