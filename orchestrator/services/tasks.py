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
from functools import partial
from http import HTTPStatus
from typing import Any
from uuid import UUID

import structlog
from celery import Celery, Task
from celery.app.control import Inspect
from celery.utils.log import get_task_logger
from kombu.serialization import registry

from orchestrator.api.error_handling import raise_status
from orchestrator.schemas.engine_settings import WorkerStatus
from orchestrator.services.processes import _get_process, _run_process_async, safe_logstep, thread_resume_process
from orchestrator.types import BroadcastFunc, State
from orchestrator.utils.json import json_dumps, json_loads
from orchestrator.workflow import ProcessStat, Success, runwf
from orchestrator.workflows import get_workflow

logger = get_task_logger(__name__)

local_logger = structlog.get_logger(__name__)

_celery: Celery | None = None

NEW_TASK = "tasks.new_task"
NEW_WORKFLOW = "tasks.new_workflow"
RESUME_TASK = "tasks.resume_task"
RESUME_WORKFLOW = "tasks.resume_workflow"


def get_celery_task(task_name: str) -> Task:
    if _celery:
        return _celery.signature(task_name)
    raise AssertionError("Celery has not been initialised yet")


def register_custom_serializer() -> None:
    # orchestrator specific serializer to correctly handle more complex classes
    registry.register("orchestrator-json", json_dumps, json_loads, "application/json", "utf-8")


def initialise_celery(celery: Celery) -> None:  # noqa: C901
    global _celery
    if _celery:
        raise AssertionError("You can only initialise Celery once")
    _celery = celery

    # Different routes/queues so we can assign them priorities
    celery.conf.task_routes = {
        NEW_TASK: {"queue": "new_tasks"},
        NEW_WORKFLOW: {"queue": "new_workflows"},
        RESUME_TASK: {"queue": "resume_tasks"},
        RESUME_WORKFLOW: {"queue": "resume_workflows"},
    }

    register_custom_serializer()

    process_broadcast_fn: BroadcastFunc | None = getattr(celery, "process_broadcast_fn", None)

    def start_process(process_id: UUID, workflow_key: str, state: dict[str, Any], user: str) -> UUID | None:
        try:
            workflow = get_workflow(workflow_key)

            if not workflow:
                raise_status(HTTPStatus.NOT_FOUND, "Workflow does not exist")

            pstat = ProcessStat(
                process_id,
                workflow=workflow,
                state=Success(state),
                log=workflow.steps,
                current_user=user,
            )

            safe_logstep_with_func = partial(safe_logstep, broadcast_func=process_broadcast_fn)
            process_id = _run_process_async(pstat.process_id, lambda: runwf(pstat, safe_logstep_with_func))

        except Exception as exc:
            local_logger.error("Worker failed to execute workflow", process_id=process_id, details=str(exc))
            return None
        else:
            return process_id

    def resume_process(process_id: UUID, user_inputs: list[State] | None, user: str) -> UUID | None:
        try:
            process = _get_process(process_id)
            process_id = thread_resume_process(
                process, user_inputs=user_inputs, user=user, broadcast_func=process_broadcast_fn
            )
        except Exception as exc:
            local_logger.error("Worker failed to resume workflow", process_id=process_id, details=str(exc))
            return None
        else:
            return process_id

    celery_task = partial(celery.task, log=local_logger, serializer="orchestrator-json")

    @celery_task(name=NEW_TASK)  # type: ignore
    def new_task(process_id, workflow_key: str, state: dict[str, Any], user: str) -> UUID | None:
        local_logger.info("Start task", process_id=process_id, workflow_key=workflow_key)
        return start_process(process_id, workflow_key, state=state, user=user)

    @celery_task(name=NEW_WORKFLOW)  # type: ignore
    def new_workflow(process_id, workflow_key: str, state: dict[str, Any], user: str) -> UUID | None:
        local_logger.info("Start workflow", process_id=process_id, workflow_key=workflow_key)
        return start_process(process_id, workflow_key, state=state, user=user)

    @celery_task(name=RESUME_TASK)  # type: ignore
    def resume_task(process_id: UUID, user_inputs: list[State] | None, user: str) -> UUID | None:
        local_logger.info("Resume task", process_id=process_id)
        return resume_process(process_id, user_inputs=user_inputs, user=user)

    @celery_task(name=RESUME_WORKFLOW)  # type: ignore
    def resume_workflow(process_id: UUID, user_inputs: list[State] | None, user: str) -> UUID | None:
        local_logger.info("Resume workflow", process_id=process_id)
        return resume_process(process_id, user_inputs=user_inputs, user=user)


class CeleryJobWorkerStatus(WorkerStatus):
    def __init__(self) -> None:
        super().__init__(executor_type="celery")
        if not _celery:
            logger.error("Can't create CeleryJobStatistics. Celery is not initialised.")
            return

        inspection: Inspect = _celery.control.inspect()
        stats = inspection.stats()
        self.number_of_workers_online = len(stats)

        def sum_items(d: dict) -> int:
            return sum(len(lines) for _, lines in d.items()) if d else 0

        self.number_of_queued_jobs = sum_items(inspection.scheduled()) + sum_items(inspection.reserved())
        self.number_of_running_jobs = sum(len(tasks) for w, tasks in inspection.active().items())
