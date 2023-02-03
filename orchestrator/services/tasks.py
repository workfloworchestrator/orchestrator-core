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

from typing import List, Optional
from uuid import UUID

import structlog
from celery import Celery, Task
from celery.utils.log import get_task_logger

from orchestrator.services.processes import _get_process, thread_resume_process, thread_start_process
from orchestrator.types import State

logger = get_task_logger(__name__)

mylogger = structlog.get_logger(__name__)


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


def initialise_celery(celery: Celery) -> None:
    global _celery
    if _celery:
        raise AssertionError("You can only initialise Celery once")
    _celery = celery

    # Different routes/queues so we can assign them priorities
    celery.conf.task_routes = {
        NEW_TASK: {"queue": "tasks"},
        NEW_WORKFLOW: {"queue": "workflows"},
        RESUME_TASK: {"queue": "tasks"},
        RESUME_WORKFLOW: {"queue": "workflows"},
    }

    def start_process(workflow_key: str, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        try:
            pid, _ = thread_start_process(workflow_key, user_inputs=user_inputs, user=user)
        except Exception:
            mylogger.error("Worked failed to execute workflow", workflow_key=workflow_key)
            return None
        else:
            return pid

    def resume_process(pid: UUID, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        try:
            process = _get_process(pid)
            pid, _ = thread_resume_process(process, user_inputs=user_inputs, user=user)
        except Exception:
            mylogger.error("Worked failed to resume workflow", pid=pid)
            return None
        else:
            return pid

    @celery.task(log=mylogger, name=NEW_TASK)  # type: ignore
    def new_task(workflow_key: str, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        mylogger.warning("Start task", workflow_key=workflow_key)
        return start_process(workflow_key, user_inputs=user_inputs, user=user)

    @celery.task(log=mylogger, name=NEW_WORKFLOW)  # type: ignore
    def new_workflow(workflow_key: str, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        mylogger.info("Start workflow", workflow_key=workflow_key)
        return start_process(workflow_key, user_inputs=user_inputs, user=user)

    @celery.task(log=mylogger, name=RESUME_TASK)  # type: ignore
    def resume_task(pid: UUID, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        mylogger.warning("Resume task")
        return resume_process(pid, user_inputs=user_inputs, user=user)

    @celery.task(log=mylogger, name=RESUME_WORKFLOW)  # type: ignore
    def resume_workflow(pid: UUID, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        mylogger.info("Resume workflow")
        return resume_process(pid, user_inputs=user_inputs, user=user)
