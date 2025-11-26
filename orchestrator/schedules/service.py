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
import logging
from uuid import UUID

from apscheduler.schedulers.base import BaseScheduler
from sqlalchemy import delete

from orchestrator import app_settings
from orchestrator.db import db
from orchestrator.db.models import WorkflowApschedulerJob
from orchestrator.schemas.schedules import APSchedulerJob
from orchestrator.services.processes import start_process
from orchestrator.utils.redis_client import create_redis_client

reddis_connection = create_redis_client(app_settings.CACHE_URI)

SCHEDULER_QUEUE = "scheduler:queue:"
SCHEDULER_Q_CREATE = "create"
SCHEDULER_Q_UPDATE = "update"
SCHEDULER_Q_DELETE = "delete"

logger = logging.getLogger(__name__)


def serialize_payload(payload: APSchedulerJob, scheduled_type: str) -> bytes:
    """Serialize the payload to bytes for Redis storage.

    Args:
        payload: APSchedulerJob The scheduled task payload.
        scheduled_type: str The type of scheduled task (create, update, delete).
    """
    payload.scheduled_type = scheduled_type
    json_dump = payload.model_dump_json()
    return json_dump.encode()


def deserialize_payload(bytes_dump: bytes) -> APSchedulerJob:
    """Deserialize the payload from bytes for Redis retrieval.

    Args:
        bytes_dump: bytes The serialized payload.
    """
    json_dump = bytes_dump.decode()
    return APSchedulerJob.model_validate_json(json_dump)


def add_create_scheduled_task_to_queue(payload: APSchedulerJob) -> None:
    """Create a scheduled task service function.

    We need to create a apscheduler job, and put the workflow and schedule_id in
    the linker table workflows_apscheduler_jobs.

    Args:
        payload: APSchedulerJob The scheduled task to create.
    """
    bytes_dump = serialize_payload(payload, SCHEDULER_Q_CREATE)
    reddis_connection.lpush(SCHEDULER_QUEUE, bytes_dump)
    logger.info("Added create scheduled task to queue.")


def add_update_scheduled_task_to_queue(payload: APSchedulerJob) -> None:
    """Update a scheduled task service function.

    Args:
        payload: APSchedulerJob The scheduled task to update.
    """
    bytes_dump = serialize_payload(payload, SCHEDULER_Q_UPDATE)
    reddis_connection.lpush(SCHEDULER_QUEUE, bytes_dump)
    logger.info("Updated scheduled task to queue.")


def add_delete_scheduled_task_to_queue(payload: APSchedulerJob) -> None:
    """Delete a scheduled task service function.

    We need to delete a apscheduler job, and remove the workflow and schedule_id in
    the linker table workflows_apscheduler_jobs.

    Args:
        payload: APSchedulerJob The scheduled task to delete.
    """
    bytes_dump = serialize_payload(payload, SCHEDULER_Q_DELETE)
    reddis_connection.lpush(SCHEDULER_QUEUE, bytes_dump)
    logger.info("Added delete scheduled task to queue.")


def _add_linker_entry(workflow_id: UUID, schedule_id: str) -> None:
    """Add an entry to the linker table workflows_apscheduler_jobs.

    Args:
        workflow_id: UUID The workflow ID.
        schedule_id: str The schedule ID.
    """
    with db.session.begin():
        workflows_apscheduler_job = WorkflowApschedulerJob(workflow_id=workflow_id, schedule_id=schedule_id)
        db.session.add(workflows_apscheduler_job)


def _delete_linker_entry(workflow_id: UUID, schedule_id: str) -> None:
    """Delete an entry from the linker table workflows_apscheduler_jobs.

    Args:
        workflow_id: UUID The workflow ID.
        schedule_id: str The schedule ID.
    """
    with db.session.begin():
        db.session.execute(
            delete(WorkflowApschedulerJob).where(
                WorkflowApschedulerJob.workflow_id == workflow_id, WorkflowApschedulerJob.schedule_id == schedule_id
            )
        )


def run_start_workflow_scheduler_task(workflow_name: str) -> None:
    """Function to start a workflow from the scheduler.

    Args:
        workflow_name: str The name of the workflow to start.
    """
    logger.info(f"Starting workflow: {workflow_name}")
    start_process(workflow_name)


def _add_scheduled_task(payload: APSchedulerJob, scheduler_connection: BaseScheduler) -> None:
    """Create a new scheduled task in the scheduler and also in the linker table.

    Args:
        payload: APSchedulerJob The scheduled task to create.
        scheduler_connection: BaseScheduler The scheduler connection.
    """
    logger.info(f"Adding scheduled task: {payload}")

    # This function is always the same for scheduled tasks, it will run the workflow
    func = run_start_workflow_scheduler_task

    # Ensure payload has required data
    if not payload.trigger or not payload.workflow_name or not payload.name or not payload.kwargs or not payload.workflow_id:
        raise ValueError("Trigger must be specified for scheduled tasks.")

    scheduler_connection.add_job(
        func=func,
        trigger=payload.trigger,
        id=payload.workflow_name,
        name=payload.name,
        kwargs={"workflow_name": payload.workflow_name},
        **(payload.kwargs or {}),
    )

    _add_linker_entry(workflow_id=payload.workflow_id, schedule_id=payload.workflow_name)


def _update_scheduled_task(payload: APSchedulerJob, scheduler_connection: BaseScheduler) -> None:
    """Update an existing scheduled task in the scheduler.

    Only allow update of name and trigger
    Job id must be that of an existing job
    Do not insert in linker table - it should already exist.

    Args:
        payload: APSchedulerJob The scheduled task to update.
        scheduler_connection: BaseScheduler The scheduler connection.
    """
    logger.info(f"Updating scheduled task: {payload}")

    job = scheduler_connection.get_job(job_id=payload.workflow_name)
    if not job:
        raise ValueError(f"Job with id {payload.workflow_name} does not exist.")

    job.modify(name=payload.name, trigger=payload.trigger)


def _delete_scheduled_task(payload: APSchedulerJob, scheduler_connection: BaseScheduler) -> None:
    """Delete an existing scheduled task in the scheduler and also in the linker table.

    Args:
        payload: APSchedulerJob The scheduled task to delete.
        scheduler_connection: BaseScheduler The scheduler connection.
    """
    logger.info(f"Deleting scheduled task: {payload}")

    scheduler_connection.remove_job(job_id=payload.workflow_name)
    _delete_linker_entry(workflow_id=payload.workflow_id, schedule_id=payload.workflow_name)


def workflow_scheduler_queue(queue_item: tuple[str, bytes], scheduler_connection: BaseScheduler) -> None:
    """Process an item from the scheduler queue.

    Args:
        queue_item: tuple[str, bytes] The item from the scheduler queue.
        scheduler_connection: BaseScheduler The scheduler connection.
    """
    try:
        _, bytes_dump = queue_item
        payload = deserialize_payload(bytes_dump)

        if payload.scheduled_type == SCHEDULER_Q_CREATE:
            _add_scheduled_task(payload, scheduler_connection)
        elif payload.scheduled_type == SCHEDULER_Q_UPDATE:
            _update_scheduled_task(payload, scheduler_connection)
        elif payload.scheduled_type == SCHEDULER_Q_DELETE:
            _delete_scheduled_task(payload, scheduler_connection)
        else:
            logger.warning(f"Unexpected schedule type: {payload.scheduled_type}")
    except Exception as e:
        logger.error(f"Error processing scheduler queue item: {e}")
