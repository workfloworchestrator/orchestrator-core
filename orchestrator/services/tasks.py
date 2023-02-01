from typing import Optional, List
from uuid import UUID

import structlog
from celery import Celery
from celery.utils.log import get_task_logger

from orchestrator.services.processes import thread_start_process
from orchestrator.settings import AppSettings
from orchestrator.types import State

logger = get_task_logger(__name__)

mylogger = structlog.get_logger(__name__)


class MyCelery(Celery):
    def on_init(self):
        # TODO: this is kinda ugly but needed to import the lazy workflows. Move this to client
        from surf import load_surf

        from orchestrator import OrchestratorCore
        app = OrchestratorCore(base_settings=AppSettings())
        load_surf(app)


celery = MyCelery('proj',
             broker='redis://',
             backend='rpc://',
             include=['orchestrator.services.tasks'])

celery.conf.task_routes = {
    "tasks.task": {'queue': 'tasks'},
    "tasks.workflow": {'queue': 'workflows'},
}

celery.conf.update(
    result_expires=3600,
)


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

