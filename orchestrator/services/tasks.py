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
    return _celery.signature(task_name)


def initialise_celery(celery: Celery) -> None:
    global _celery
    assert not _celery, "You can only initialise Celery once"
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
        except Exception as exc:
            return exc.detail
        else:
            return pid

    def resume_process(pid: UUID, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        try:
            process = _get_process(pid)
            pid, _ = thread_resume_process(process, user_inputs=user_inputs, user=user)
        except Exception as exc:
            return exc.detail
        else:
            return pid

    @celery.task(log=mylogger, name=NEW_TASK)
    def new_task(workflow_key: str, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        mylogger.warning("Start task", workflow_key=workflow_key)
        return start_process(workflow_key, user_inputs=user_inputs, user=user)

    @celery.task(log=mylogger, name=NEW_WORKFLOW)
    def new_workflow(workflow_key: str, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        mylogger.info("Start workflow", workflow_key=workflow_key)
        return start_process(workflow_key, user_inputs=user_inputs, user=user)

    @celery.task(log=mylogger, name=RESUME_TASK)
    def resume_task(pid: UUID, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        mylogger.warning("Resume task")
        return resume_process(pid, user_inputs=user_inputs, user=user)

    @celery.task(log=mylogger, name=RESUME_WORKFLOW)
    def resume_workflow(pid: UUID, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        mylogger.info("Resume workflow")
        return resume_process(pid, user_inputs=user_inputs, user=user)
