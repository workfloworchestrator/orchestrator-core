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
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from celery import Celery, Task
from celery.utils.log import get_task_logger
from kombu.serialization import registry

from orchestrator.api.error_handling import raise_status
from orchestrator.services.processes import _get_process, _run_process_async, safe_logstep, thread_resume_process
from orchestrator.types import State
from orchestrator.utils.json import json_dumps, json_loads
from orchestrator.workflow import ProcessStat, Success, runwf
from orchestrator.workflows import get_workflow

logger = get_task_logger(__name__)

local_logger = structlog.get_logger(__name__)


_celery: Optional[Celery] = None


NEW_TASK = "tasks.new_task"
NEW_WORKFLOW = "tasks.new_workflow"
RESUME_TASK = "tasks.resume_task"
RESUME_WORKFLOW = "tasks.resume_workflow"


def get_celery_task(task_name: str) -> Task:
    if _celery:
        return _celery.signature(task_name)
    else:
        raise AssertionError("Celery has not been initialised yet")


def register_custom_serializer() -> None:
    # surf specific serializer to correctly handle more complex classes
    registry.register("surf", json_dumps, json_loads, "application/json", "utf-8")


def initialise_celery(celery: Celery) -> None:
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

    def start_process(pid: UUID, workflow_key: str, state: Dict[str, Any], user: str) -> Optional[UUID]:
        try:
            workflow = get_workflow(workflow_key)

            if not workflow:
                raise_status(HTTPStatus.NOT_FOUND, "Workflow does not exist")

            pstat = ProcessStat(pid, workflow=workflow, state=Success(state), log=workflow.steps, current_user=user)

            safe_logstep_with_func = partial(safe_logstep, broadcast_func=None)
            pid = _run_process_async(pstat.pid, lambda: runwf(pstat, safe_logstep_with_func))

        except Exception as exc:
            local_logger.error("Worker failed to execute workflow", pid=pid, details=str(exc))
            return None
        else:
            return pid

    def resume_process(pid: UUID, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        try:
            process = _get_process(pid)
            pid = thread_resume_process(process, user_inputs=user_inputs, user=user)
        except Exception as exc:
            local_logger.error("Worker failed to resume workflow", pid=pid, details=str(exc))
            return None
        else:
            return pid

    @celery.task(log=local_logger, name=NEW_TASK, serializer="surf")  # type: ignore
    def new_task(pid, workflow_key: str, state: Dict[str, Any], user: str) -> Optional[UUID]:
        local_logger.info("Start task", pid=pid, workflow_key=workflow_key)
        return start_process(pid, workflow_key, state=state, user=user)

    @celery.task(log=local_logger, name=NEW_WORKFLOW, serializer="surf")  # type: ignore
    def new_workflow(pid, workflow_key: str, state: Dict[str, Any], user: str) -> Optional[UUID]:
        local_logger.info("Start workflow", pid=pid, workflow_key=workflow_key)
        return start_process(pid, workflow_key, state=state, user=user)

    @celery.task(log=local_logger, name=RESUME_TASK)  # type: ignore
    def resume_task(pid: UUID, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        local_logger.info("Resume task", pid=pid)
        return resume_process(pid, user_inputs=user_inputs, user=user)

    @celery.task(log=local_logger, name=RESUME_WORKFLOW)  # type: ignore
    def resume_workflow(pid: UUID, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        local_logger.info("Resume workflow", pid=pid)
        return resume_process(pid, user_inputs=user_inputs, user=user)
