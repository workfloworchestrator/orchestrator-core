from inspect import Signature
from typing import List, Optional
from uuid import UUID

import structlog
from celery import Celery, Task
from celery.utils.log import get_task_logger

from orchestrator.services.processes import thread_start_process
from orchestrator.settings import AppSettings
from orchestrator.types import State

logger = get_task_logger(__name__)

mylogger = structlog.get_logger(__name__)


_celery: Optional[Celery] = None


def get_celery_task(task_name: str) -> Task:
    return _celery.signature(task_name)


def initialise_celery(celery: Celery) -> None:
    global _celery
    assert not _celery, "You can only initialise Celery once"
    _celery = celery

    celery.conf.task_routes = {
        "tasks.task": {'queue': 'tasks'},
        "tasks.workflow": {'queue': 'workflows'},
    }

    @celery.task(log=mylogger, name="tasks.task")
    def trigger_celery_task(workflow_key: str, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        mylogger.warning("Started task!", workflow_key=workflow_key)

        try:
            pid, _ = thread_start_process(workflow_key, user_inputs=user_inputs, user=user)
        except Exception as exc:
            return exc.detail
        else:
            return pid

    @celery.task(log=mylogger, name="tasks.workflow")
    def trigger_celery_workflow(workflow_key: str, user_inputs: Optional[List[State]], user: str) -> Optional[UUID]:
        mylogger.info("Started workflow", workflow_key=workflow_key)

        try:
            pid, _ = thread_start_process(workflow_key, user_inputs=user_inputs, user=user)
        except Exception as exc:
            return exc.detail
        else:
            return pid


