# Copyright 2019-2025 SURF.
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
import json
import logging
from uuid import UUID, uuid4

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import delete

from orchestrator import app_settings
from orchestrator.db import db
from orchestrator.db.models import WorkflowApschedulerJob
from orchestrator.schemas.schedules import (
    APSchedulerJobCreate,
    APSchedulerJobDelete,
    APSchedulerJobs,
    APSchedulerJobUpdate,
    APSJobAdapter,
)
from orchestrator.services.processes import start_process
from orchestrator.services.workflows import get_workflow_by_workflow_id
from orchestrator.utils.redis_client import create_redis_client

redis_connection = create_redis_client(app_settings.CACHE_URI.get_secret_value())

SCHEDULER_QUEUE = "scheduler:queue:"


logger = logging.getLogger(__name__)


def serialize_payload(payload: APSchedulerJobs) -> bytes:
    """Serialize the payload to bytes for Redis storage.

    Args:
        payload: APSchedulerJobs The scheduled task payload.
    """
    data = json.loads(payload.model_dump_json())
    data["scheduled_type"] = payload.scheduled_type
    return json.dumps(data).encode()


def deserialize_payload(bytes_dump: bytes) -> APSchedulerJobs:
    """Deserialize the payload from bytes for Redis retrieval.

    Args:
        bytes_dump: bytes The serialized payload.
    """
    json_dump = bytes_dump.decode()
    return APSJobAdapter.validate_json(json_dump)


def add_scheduled_task_to_queue(payload: APSchedulerJobs) -> None:
    """Create a scheduled task service function.

    We need to create, update or delete an apscheduler job, and put the
    workflow and schedule_id in the linker table workflows_apscheduler_jobs.
    This is done by adding a job to a redis queue which will be executed
    when the scheduler runs.

    Args:
        payload: APSchedulerJobs The scheduled task to create, update or delete
    """
    bytes_dump = serialize_payload(payload)
    redis_connection.lpush(SCHEDULER_QUEUE, bytes_dump)
    logger.info("Added scheduled task to queue.")


def add_unique_scheduled_task_to_queue(payload: APSchedulerJobCreate) -> bool:
    """Create a unique scheduled task service function.

    Checks if the workflow is already scheduled before creating an apscheduler
    job, and putting the workflow and schedule_id in the linker table
    workflows_apscheduler_jobs.
    This is done by adding a job to a redis queue which will be executed
    when the scheduler runs.

    This function is not safe for concurrent usage and when the scheduler is not
    running, as there might be a race condition between adding a job and checking
    if it already exists in the database.

    Args:
        payload: APSchedulerJobCreate The scheduled task to create.

    Returns:
        True when the scheduled task was added to the queue
        False when the scheduled task was not added to the queue
    """
    if db.session.query(WorkflowApschedulerJob).filter_by(workflow_id=payload.workflow_id).all():
        logger.info(f"Not adding existing workflow {payload.workflow_name} as scheduled task.")
        return False
    add_scheduled_task_to_queue(payload)
    return True


def get_linker_entries_by_schedule_ids(schedule_ids: list[str]) -> list[WorkflowApschedulerJob]:
    """Get linker table entries for multiple schedule IDs in a single query.

    Args:
        schedule_ids: list[str] — One or many schedule IDs.

    Returns:
        list[WorkflowApschedulerJob]: All linker table rows matching those IDs.
    """
    if not schedule_ids:
        return []

    return db.session.query(WorkflowApschedulerJob).filter(WorkflowApschedulerJob.schedule_id.in_(schedule_ids)).all()


def _add_linker_entry(workflow_id: UUID, schedule_id: str) -> None:
    """Add an entry to the linker table workflows_apscheduler_jobs.

    Args:
        workflow_id: UUID The workflow ID.
        schedule_id: str The schedule ID.
    """
    workflows_apscheduler_job = WorkflowApschedulerJob(workflow_id=workflow_id, schedule_id=schedule_id)
    db.session.add(workflows_apscheduler_job)
    db.session.commit()


def _delete_linker_entry(workflow_id: UUID, schedule_id: str) -> None:
    """Delete an entry from the linker table workflows_apscheduler_jobs.

    Args:
        workflow_id: UUID The workflow ID.
        schedule_id: str The schedule ID.
    """
    db.session.execute(
        delete(WorkflowApschedulerJob).where(
            WorkflowApschedulerJob.workflow_id == workflow_id, WorkflowApschedulerJob.schedule_id == schedule_id
        )
    )
    db.session.commit()


def run_start_workflow_scheduler_task(workflow_name: str) -> None:
    """Function to start a workflow from the scheduler.

    Args:
        workflow_name: str The name of the workflow to start.
    """
    logger.info(f"Starting workflow: {workflow_name}")
    start_process(workflow_name)


def _add_scheduled_task(payload: APSchedulerJobCreate, scheduler_connection: BaseScheduler) -> None:
    """Create a new scheduled task in the scheduler and also in the linker table.

    Args:
        payload: APSchedulerJobCreate The scheduled task to create.
        scheduler_connection: BaseScheduler The scheduler connection.
    """
    logger.info(f"Adding scheduled task: {payload}")

    workflow_description = None
    # Check if a workflow exists - we cannot schedule a non-existing workflow
    workflow = get_workflow_by_workflow_id(str(payload.workflow_id))
    if not workflow:
        raise ValueError(f"Workflow with id {payload.workflow_id} does not exist.")
    workflow_description = workflow.description

    # This function is always the same for scheduled tasks, it will run the workflow
    func = run_start_workflow_scheduler_task

    # Ensure payload has required data
    if not payload.trigger or not payload.workflow_name or not payload.trigger_kwargs or not payload.workflow_id:
        raise ValueError("Trigger must be specified for scheduled tasks.")

    schedule_id = str(uuid4())
    scheduler_connection.add_job(
        func=func,
        trigger=payload.trigger,
        id=schedule_id,
        name=payload.name or workflow_description,
        kwargs={"workflow_name": payload.workflow_name},
        **(payload.trigger_kwargs or {}),
    )

    _add_linker_entry(workflow_id=payload.workflow_id, schedule_id=schedule_id)


def _build_trigger_on_update(
    trigger_name: str | None, trigger_kwargs: dict
) -> IntervalTrigger | CronTrigger | DateTrigger | None:
    if not trigger_name or not trigger_kwargs:
        logger.info("Skipping building trigger as no trigger information is provided.")
        return None

    match trigger_name:
        case "interval":
            return IntervalTrigger(**trigger_kwargs)
        case "cron":
            return CronTrigger(**trigger_kwargs)
        case "date":
            return DateTrigger(**trigger_kwargs)
        case _:
            raise ValueError(f"Invalid trigger type: {trigger_name}")


def _update_scheduled_task(payload: APSchedulerJobUpdate, scheduler_connection: BaseScheduler) -> None:
    """Update an existing scheduled task in the scheduler.

    Only allow update of name and trigger
    Job id must be that of an existing job
    Do not insert in linker table - it should already exist.

    Args:
        payload: APSchedulerJobUpdate The scheduled task to update.
        scheduler_connection: BaseScheduler The scheduler connection.
    """
    logger.info(f"Updating scheduled task: {payload}")

    schedule_id = str(payload.schedule_id)
    job = scheduler_connection.get_job(job_id=schedule_id)
    if not job:
        raise ValueError(f"Schedule Job with id {schedule_id} does not exist.")

    trigger = _build_trigger_on_update(payload.trigger, payload.trigger_kwargs or {})
    modify_kwargs = {}

    if trigger:
        job = job.reschedule(trigger=trigger)

    if payload.name:
        modify_kwargs["name"] = payload.name

    job.modify(**modify_kwargs)


def _delete_scheduled_task(payload: APSchedulerJobDelete, scheduler_connection: BaseScheduler) -> None:
    """Delete an existing scheduled task in the scheduler and also in the linker table.

    Args:
        payload: APSchedulerJobDelete The scheduled task to delete.
        scheduler_connection: BaseScheduler The scheduler connection.
    """
    logger.info(f"Deleting scheduled task: {payload}")

    schedule_id = str(payload.schedule_id)
    scheduler_connection.remove_job(job_id=schedule_id)
    _delete_linker_entry(workflow_id=payload.workflow_id, schedule_id=schedule_id)


def workflow_scheduler_queue(queue_item: tuple[str, bytes], scheduler_connection: BaseScheduler) -> None:
    """Process an item from the scheduler queue.

    Args:
        queue_item: tuple[str, bytes] The item from the scheduler queue.
        scheduler_connection: BaseScheduler The scheduler connection.
    """
    try:
        _, bytes_dump = queue_item
        payload = deserialize_payload(bytes_dump)
        match payload:
            case APSchedulerJobCreate():
                _add_scheduled_task(payload, scheduler_connection)

            case APSchedulerJobUpdate():
                _update_scheduled_task(payload, scheduler_connection)

            case APSchedulerJobDelete():
                _delete_scheduled_task(payload, scheduler_connection)

            case _:
                logger.warning(f"Unexpected schedule type: {payload}")  # type: ignore
    except Exception:
        logger.exception("Error processing scheduler queue item")
