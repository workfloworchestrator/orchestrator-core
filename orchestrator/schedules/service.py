import logging
import time

from typing import Any, Literal, Dict
from uuid import UUID

import sqlalchemy
from pydantic import BaseModel, Field

from apscheduler.schedulers.base import BaseScheduler
from orchestrator import app_settings

from orchestrator.services.processes import start_process
from orchestrator.db import db

from orchestrator.utils.redis_client import create_redis_client, Redis
from redis.exceptions import ConnectionError

reddis_connection = create_redis_client(app_settings.CACHE_URI)

SCHEDULER_QUEUE = "scheduler:queue:"
SCHEDULER_Q_CREATE = "scheduler:queue:create_scheduled_task"
SCHEDULER_Q_UPDATE = "scheduler:queue:update_scheduled_task"
SCHEDULER_Q_DELETE = "scheduler:queue:delete_scheduled_task"

logger = logging.getLogger(__name__)


class APSchedulerJob(BaseModel):
    process_name: str = Field(..., description="ID/name of the process to run e.g. 'my_process'")
    workflow_id: UUID | None = Field(
        None, description="UUID of the workflow associated with this scheduled task"
    )

    name: str | None = Field(
        None, description="Human readable name e.g. 'My Process'"
    )

    trigger: Literal["interval", "cron", "date"] | None = Field(
        None, description="APScheduler trigger type"
    )

    kwargs: Dict[str, Any] | None = Field(
        default_factory=dict, description="Arguments passed to the job function"
    )

    scheduled_type: Literal["create", "update", "delete"] | None = Field(
        None, description="Type of scheduled task operation"
    )


def serialize_payload(payload: APSchedulerJob, scheduled_type: str) -> bytes:
    """Serialize the payload to bytes for Redis storage."""
    json_dump = payload.model_dump_json()
    bytes_dump = json_dump.encode()
    return bytes_dump


def deserialize_payload(bytes_dump) -> APSchedulerJob:
    """Deserialize the payload from bytes for Redis retrieval."""
    json_dump = bytes_dump.decode()
    payload = APSchedulerJob.model_validate_json(json_dump)
    return payload


def add_create_scheduled_task_to_queue(payload: APSchedulerJob):
    """Create a scheduled task service function.

    We need to create a apscheduler job, and put the workflow and schedule_id in
    the linker table workflows_apscheduler_jobs.

    Args:
        :param payload: APSchedulerJob The scheduled task to create.
    """
    bytes_dump = serialize_payload(payload, SCHEDULER_Q_CREATE)
    reddis_connection.lpush(SCHEDULER_QUEUE, bytes_dump)
    logger.info("Added create scheduled task to queue.")


def add_update_scheduled_task_to_queue(payload: APSchedulerJob):
    """Update a scheduled task service function.

    Args
        :param payload: APSchedulerJob The scheduled task to update.
    """
    bytes_dump = serialize_payload(payload, SCHEDULER_Q_UPDATE)
    reddis_connection.lpush(SCHEDULER_QUEUE, bytes_dump)
    logger.info("Updated scheduled task to queue.")


def add_delete_scheduled_task_to_queue(payload: APSchedulerJob):
    """Delete a scheduled task service function.

    We need to delete a apscheduler job, and remove the workflow and schedule_id in
    the linker table workflows_apscheduler_jobs.

    Args
        :param payload: APSchedulerJob The scheduled task to delete.
    """
    bytes_dump = serialize_payload(payload, SCHEDULER_Q_DELETE)
    reddis_connection.lpush(SCHEDULER_QUEUE, bytes_dump)
    logger.info("Added delete scheduled task to queue.")


def add_linker_entry(workflow_id: UUID, schedule_id: str):
    query = """
            INSERT INTO workflows_apscheduler_jobs (workflow_id, schedule_id)
            VALUES (:workflow_id, :schedule_id)
            ON CONFLICT DO NOTHING;
            """

    with db._engine.begin() as conn:
        conn.execute(
            sqlalchemy.text(query),
            {"workflow_id": workflow_id, "schedule_id": schedule_id},
        )


def delete_linker_entry(workflow_id: UUID, schedule_id: str):
    query = """
            DELETE FROM workflows_apscheduler_jobs
            WHERE workflow_id = :workflow_id
              AND schedule_id = :schedule_id; \
            """

    with db._engine.begin() as conn:
        conn.execute(
            sqlalchemy.text(query),
            {"workflow_id": workflow_id, "schedule_id": schedule_id},
        )


def run_start_process_scheduler_task(process_name: str) -> None:
    logger.info(f"Starting process scheduler task: {process_name}")
    start_process(process_name)


def add_scheduled_task(payload: APSchedulerJob, scheduler_connection: BaseScheduler):
    """Create a new scheduled task in the scheduler and also in the linker table."""
    logger.info(f"Adding scheduled task: {payload}")

    # This function is always the same for scheduled tasks, it will run the
    func = run_start_process_scheduler_task

    # Ensure payload has required data
    if (
            not payload.trigger or
            not payload.process_name or
            not payload.name or
            not payload.kwargs
    ):
        raise ValueError("Trigger must be specified for scheduled tasks.")

    scheduler_connection.add_job(
        func=func,
        trigger=payload.trigger,
        id=payload.process_name,
        name=payload.name,
        kwargs=payload.kwargs,
        **{"process_name": payload.process_name}
    )



def update_scheduled_task(payload, scheduler_connection: BaseScheduler):
    """Update an existing scheduled task in the scheduler.

    Only allow update of name and trigger
    Job id must be that of an existing job
    Do not insert in linker table - it should already exist."""
    logger.info(f"Updating scheduled task: {payload}")

    job = scheduler_connection.get_job(job_id=payload.process_name)
    if not job:
        raise ValueError(f"Job with id {payload.process_name} does not exist.")

    job.modify(
        name=payload.name,
        trigger=payload.trigger,
        **payload.trigger_args
    )


def delete_scheduled_task(payload, scheduler_connection: BaseScheduler):
    """Delete an existing scheduled task in the scheduler and also in the linker table."""
    logger.info(f"Deleting scheduled task: {payload}")

    scheduler_connection.remove_job(job_id=payload.process_name)


def process_scheduler_queue(queue_item: tuple[str, bytes], scheduler_connection: BaseScheduler):
    redis_queue_key, bytes_dump = queue_item
    payload = deserialize_payload(bytes_dump)

    if redis_queue_key == SCHEDULER_Q_CREATE:
        add_scheduled_task(payload, scheduler_connection)
    elif redis_queue_key == SCHEDULER_Q_UPDATE:
        update_scheduled_task(payload, scheduler_connection)
    elif redis_queue_key == SCHEDULER_Q_DELETE:
        delete_scheduled_task(payload, scheduler_connection)
    else:
        logger.warning(f"Unexpected redis queue key: {redis_queue_key}")
