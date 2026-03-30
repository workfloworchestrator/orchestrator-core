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
from functools import partial
from uuid import UUID

import structlog
from celery import Celery, Task
from celery.app.control import Inspect
from celery.utils.log import get_task_logger
from kombu.serialization import registry

from orchestrator.db import db
from orchestrator.schemas.engine_settings import WorkerStatus
from orchestrator.services.executors.threadpool import prepare_resume, prepare_start
from orchestrator.services.processes import (
    START_WORKFLOW_REMOVED_ERROR_MSG,
    _get_process,
    _run_process_async,
    ensure_correct_process_status,
    load_process,
)
from orchestrator.types import BroadcastFunc
from orchestrator.utils.json import json_dumps, json_loads
from orchestrator.workflow import ProcessStatus, runwf
from orchestrator.workflows.removed_workflow import removed_workflow

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

    def start_process(process_id: UUID, user: str) -> UUID | None:
        try:
            # Use a database scope only for the pre-workflow setup (loading process, checking
            # status, retrieving input state, marking RUNNING). The scope closes before the
            # workflow runs, returning the connection to the pool. _run_process_async creates
            # its own scope for the actual workflow execution — no nested scopes, no wasted
            # connections sitting "idle in transaction" for the duration of the workflow.
            with db.database_scope():
                process = _get_process(process_id)
                pstat = load_process(process)
                ensure_correct_process_status(process_id, ProcessStatus.CREATED)
                if pstat.workflow == removed_workflow:
                    raise ValueError(START_WORKFLOW_REMOVED_ERROR_MSG)
                pstat, logstep_func = prepare_start(pstat, broadcast_func=process_broadcast_fn)
            # Scope closed — connection returned to pool before workflow runs
            _run_process_async(pstat.process_id, lambda: runwf(pstat, logstep_func))
        except Exception as exc:
            local_logger.error("Worker failed to execute workflow", process_id=process_id, details=str(exc))
            return None
        else:
            return process_id

    def resume_process(process_id: UUID, user: str) -> UUID | None:
        try:
            with db.database_scope():
                process = _get_process(process_id)
                ensure_correct_process_status(process_id, ProcessStatus.RESUMED)
                pstat, logstep_func = prepare_resume(process, user=user, broadcast_func=process_broadcast_fn)
            # Scope closed — connection returned to pool before workflow runs
            _run_process_async(pstat.process_id, lambda: runwf(pstat, logstep_func))
        except Exception as exc:
            local_logger.error("Worker failed to resume workflow", process_id=process_id, details=str(exc))
            return None
        else:
            return process_id

    celery_task = partial(celery.task, log=local_logger, serializer="orchestrator-json")

    @celery_task(name=NEW_TASK)  # type: ignore
    def new_task(process_id: UUID, user: str) -> UUID | None:
        local_logger.info("Start task", process_id=process_id)
        return start_process(process_id, user=user)

    @celery_task(name=NEW_WORKFLOW)  # type: ignore
    def new_workflow(process_id: UUID, user: str) -> UUID | None:
        local_logger.info("Start workflow", process_id=process_id)
        return start_process(process_id, user=user)

    @celery_task(name=RESUME_TASK)  # type: ignore
    def resume_task(process_id: UUID, user: str) -> UUID | None:
        local_logger.info("Resume task", process_id=process_id)
        return resume_process(process_id, user=user)

    @celery_task(name=RESUME_WORKFLOW)  # type: ignore
    def resume_workflow(process_id: UUID, user: str) -> UUID | None:
        local_logger.info("Resume workflow", process_id=process_id)
        return resume_process(process_id, user=user)


class CeleryJobWorkerStatus(WorkerStatus):
    def __init__(self) -> None:
        super().__init__(executor_type="celery")
        if not _celery:
            logger.error("Can't create CeleryJobStatistics. Celery is not initialised.")
            return

        inspection: Inspect = _celery.control.inspect()
        stats = inspection.stats()
        scheduled = inspection.scheduled()
        reserved = inspection.reserved()
        active = inspection.active()

        results = {"stats": stats, "scheduled": scheduled, "reserver": reserved, "active": active}

        if any(value is None for value in results.values()):
            logger.warning("Celery inspect results incomplete, missing values will default to 0. Results: %s", results)
        else:
            logger.debug("Celery inspect results complete. Results: %s", results)

        self.number_of_workers_online = len(stats) if stats else 0

        def sum_items(d: dict | None) -> int:
            return sum(len(lines) for _, lines in d.items()) if d else 0

        self.number_of_queued_jobs = sum_items(scheduled) + sum_items(reserved)
        self.number_of_running_jobs = sum(len(tasks) for w, tasks in active.items()) if active else 0
