from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from orchestrator.db import db
from orchestrator.db.models import WorkflowApschedulerJob
from orchestrator.schedules.scheduler import enrich_with_workflow_id, get_scheduler
from orchestrator.schedules.service import (
    SCHEDULER_QUEUE,
    _add_scheduled_task,
    _build_trigger_on_update,
    _delete_scheduled_task,
    _update_scheduled_task,
    add_scheduled_task_to_queue,
    add_unique_scheduled_task_to_queue,
    deserialize_payload,
    get_linker_entries_by_schedule_ids,
    run_start_workflow_scheduler_task,
    serialize_payload,
    workflow_scheduler_queue,
)
from orchestrator.schemas.schedules import (
    SCHEDULER_Q_CREATE,
    SCHEDULER_Q_DELETE,
    SCHEDULER_Q_UPDATE,
    APSchedulerJobCreate,
    APSchedulerJobDelete,
    APSchedulerJobUpdate,
)
from orchestrator.services.workflows import get_workflow_by_name


def test_serialize_deserialize_payload_create():
    payload_create = APSchedulerJobCreate(
        name="Test create",
        workflow_name="wf",
        workflow_id=uuid4(),
        trigger="interval",
        trigger_kwargs={"seconds": 10},
    )
    payload_update = APSchedulerJobUpdate(
        name="Test update",
        trigger="interval",
        trigger_kwargs={"seconds": 10},
        schedule_id=uuid4(),
    )
    payload_delete = APSchedulerJobDelete(workflow_id=uuid4(), schedule_id=uuid4())

    serialized_create = serialize_payload(payload_create)
    serialized_update = serialize_payload(payload_update)
    serialized_delete = serialize_payload(payload_delete)

    assert isinstance(deserialize_payload(serialized_create), APSchedulerJobCreate)
    assert isinstance(deserialize_payload(serialized_update), APSchedulerJobUpdate)
    assert isinstance(deserialize_payload(serialized_delete), APSchedulerJobDelete)

    assert deserialize_payload(serialized_create).scheduled_type == SCHEDULER_Q_CREATE
    assert deserialize_payload(serialized_update).scheduled_type == SCHEDULER_Q_UPDATE
    assert deserialize_payload(serialized_delete).scheduled_type == SCHEDULER_Q_DELETE


@patch("orchestrator.schedules.service.redis_connection")
def test_add_create_scheduled_task_to_queue_raw(mock_redis):
    payload = APSchedulerJobCreate(
        name="Test Job",
        workflow_name="wf",
        workflow_id=uuid4(),
        trigger="interval",
        trigger_kwargs={"seconds": 5},
    )

    add_scheduled_task_to_queue(payload)

    # Extract call args
    queue, bytes_arg = mock_redis.lpush.call_args[0]

    assert queue == SCHEDULER_QUEUE
    assert isinstance(bytes_arg, bytes)
    assert b"workflow_name" in bytes_arg


@patch("orchestrator.schedules.service.redis_connection")
def test_add_update_scheduled_task_to_queue(mock_redis):
    payload = APSchedulerJobUpdate(
        name="Test Job Update",
        trigger="interval",
        trigger_kwargs={"seconds": 15},
        schedule_id=uuid4(),
    )

    add_scheduled_task_to_queue(payload)

    queue, bytes_arg = mock_redis.lpush.call_args[0]

    assert queue == SCHEDULER_QUEUE
    assert isinstance(bytes_arg, bytes)
    assert b"schedule_id" in bytes_arg


@patch("orchestrator.schedules.service.redis_connection")
def test_add_delete_scheduled_task_to_queue(mock_redis):
    payload = APSchedulerJobDelete(
        workflow_id=uuid4(),
        schedule_id=uuid4(),
    )

    add_scheduled_task_to_queue(payload)

    queue, bytes_arg = mock_redis.lpush.call_args[0]

    assert queue == SCHEDULER_QUEUE
    assert isinstance(bytes_arg, bytes)
    assert b"workflow_id" in bytes_arg


def test_get_linker_entries_by_schedule_ids(scheduler_with_jobs):
    workflow_name = "task_validate_products"
    workflow = get_workflow_by_name(workflow_name)

    schedule_id = f"{uuid4()}"
    scheduler_with_jobs(schedule_id=schedule_id)

    workflows_apscheduler_job = WorkflowApschedulerJob(workflow_id=workflow.workflow_id, schedule_id=schedule_id)
    db.session.add(workflows_apscheduler_job)

    linker_entries = get_linker_entries_by_schedule_ids([schedule_id])

    assert len(linker_entries) == 1
    assert linker_entries[0].schedule_id == schedule_id


@patch("orchestrator.schedules.service.start_process")
def test_run_start_workflow_scheduler_task_calls_start_process_once(mock_start):
    workflow_name = "task_validate_products"

    run_start_workflow_scheduler_task(workflow_name)

    mock_start.assert_called_once_with(workflow_name)


@patch("orchestrator.schedules.service._add_linker_entry", return_value=None)
@patch("orchestrator.schedules.service.get_workflow_by_workflow_id")
@patch("orchestrator.schedules.service.db.session.begin")
def test_add_scheduled_task_creates_scheduler_job_and_linker_entry(
    mock_linker_entry, mock_get_workflow, mock_db_begin, clear_all_scheduler_jobs
):
    clear_all_scheduler_jobs()

    workflow_name = "task_validate_products"
    workflow = get_workflow_by_name(workflow_name)

    # Fake workflow object returned by get_workflow_by_workflow_id
    fake_workflow = Mock()
    fake_workflow.description = "Fake workflow description"
    mock_get_workflow.return_value = fake_workflow

    payload_create = APSchedulerJobCreate(
        name=f"Some {uuid4()} hard to guess {uuid4()} Name. Test create",
        workflow_name=workflow_name,
        workflow_id=workflow.workflow_id,
        trigger="interval",
        trigger_kwargs={"seconds": 10},
    )

    with get_scheduler() as scheduler:
        _add_scheduled_task(payload_create, scheduler)

        assert len(scheduler.get_jobs()) == 1
        assert scheduler.get_jobs()[0].name == payload_create.name


@patch("orchestrator.schedules.service._build_trigger_on_update")
def test_update_scheduled_task_updates_trigger_and_name(mock_build_trigger):
    # Fake trigger returned by _build_trigger_on_update
    fake_trigger = Mock()
    mock_build_trigger.return_value = fake_trigger

    schedule_id = uuid4()

    mock_job = Mock()
    mock_job.reschedule = Mock(return_value=mock_job)
    mock_job.modify = Mock()

    # Mock scheduler
    mock_scheduler = Mock()
    mock_scheduler.get_job = Mock(return_value=mock_job)

    payload = APSchedulerJobUpdate(
        schedule_id=schedule_id,
        name="Updated Name",
        trigger="interval",
        trigger_kwargs={"seconds": 20},
    )

    _update_scheduled_task(payload, mock_scheduler)

    mock_scheduler.get_job.assert_called_once_with(job_id=str(schedule_id))
    mock_build_trigger.assert_called_once_with("interval", {"seconds": 20})
    mock_job.reschedule.assert_called_once_with(trigger=fake_trigger)
    mock_job.modify.assert_called_once_with(name="Updated Name")


@patch("orchestrator.schedules.service._delete_linker_entry")
def test_delete_scheduled_task_calls_remove_and_linker_delete(mock_delete_linker_entry):
    # --- Arrange ---
    schedule_id = uuid4()
    workflow_id = uuid4()

    payload = APSchedulerJobDelete(schedule_id=schedule_id, workflow_id=workflow_id)

    mock_scheduler = Mock()
    mock_scheduler.remove_job = Mock()

    # --- Act ---
    _delete_scheduled_task(payload, mock_scheduler)

    # --- Assert scheduler job removal ---
    mock_scheduler.remove_job.assert_called_once_with(job_id=str(schedule_id))

    # --- Assert linker entry removal ---
    mock_delete_linker_entry.assert_called_once_with(workflow_id=workflow_id, schedule_id=str(schedule_id))


def test_build_trigger_on_update_interval():
    trigger = _build_trigger_on_update("interval", {"seconds": 10})
    assert isinstance(trigger, IntervalTrigger)
    assert trigger.interval.total_seconds() == 10


def test_build_trigger_on_update_cron():
    trigger = _build_trigger_on_update("cron", {"hour": 5, "minute": 30})
    assert isinstance(trigger, CronTrigger)

    trigger_str = str(trigger)

    assert "hour='5'" in trigger_str
    assert "minute='30'" in trigger_str


def test_build_trigger_on_update_date():
    trigger = _build_trigger_on_update("date", {"run_date": "2025-01-01 10:00:00"})
    assert isinstance(trigger, DateTrigger)
    assert str(trigger.run_date).startswith("2025-01-01 10:00:00")


def test_build_trigger_on_update_none_returns_none():
    assert _build_trigger_on_update(None, {"seconds": 10}) is None
    assert _build_trigger_on_update("interval", None) is None
    assert _build_trigger_on_update("interval", {}) is None


def test_build_trigger_on_update_invalid_name():
    with pytest.raises(ValueError) as exc:
        _build_trigger_on_update("unknown", {"seconds": 10})

    assert "Invalid trigger type" in str(exc.value)


@patch("orchestrator.schedules.service._add_scheduled_task")
@patch("orchestrator.schedules.service._update_scheduled_task")
@patch("orchestrator.schedules.service._delete_scheduled_task")
def test_workflow_scheduler_queue_create(mock_delete, mock_update, mock_create):
    payload = APSchedulerJobCreate(
        name="Test",
        workflow_name="wf",
        workflow_id=uuid4(),
        trigger="interval",
        trigger_kwargs={"seconds": 10},
    )
    serialized = serialize_payload(payload)

    scheduler = Mock()

    workflow_scheduler_queue(("queue", serialized), scheduler)

    mock_create.assert_called_once()
    mock_update.assert_not_called()
    mock_delete.assert_not_called()


@patch("orchestrator.schedules.service._add_scheduled_task")
@patch("orchestrator.schedules.service._update_scheduled_task")
@patch("orchestrator.schedules.service._delete_scheduled_task")
def test_workflow_scheduler_queue_update(mock_delete, mock_update, mock_create):
    payload = APSchedulerJobUpdate(
        schedule_id=uuid4(),
        name="Test Update",
        trigger="interval",
        trigger_kwargs={"seconds": 20},
    )
    serialized = serialize_payload(payload)

    scheduler = Mock()

    workflow_scheduler_queue(("queue", serialized), scheduler)

    mock_update.assert_called_once()
    mock_create.assert_not_called()
    mock_delete.assert_not_called()


@patch("orchestrator.schedules.service._add_scheduled_task")
@patch("orchestrator.schedules.service._update_scheduled_task")
@patch("orchestrator.schedules.service._delete_scheduled_task")
def test_workflow_scheduler_queue_delete(mock_delete, mock_update, mock_create):
    payload = APSchedulerJobDelete(
        schedule_id=uuid4(),
        workflow_id=uuid4(),
    )
    serialized = serialize_payload(payload)

    scheduler = Mock()

    workflow_scheduler_queue(("queue", serialized), scheduler)

    mock_delete.assert_called_once()
    mock_update.assert_not_called()
    mock_create.assert_not_called()


def test_enrich_schedule_with_workflow_id(scheduler_with_jobs, clear_all_scheduler_jobs):
    clear_all_scheduler_jobs()

    workflow_name = "task_validate_products"
    workflow = get_workflow_by_name(workflow_name)

    schedule_id = f"{uuid4()}"
    scheduler_with_jobs(schedule_id=schedule_id)

    workflows_apscheduler_job = WorkflowApschedulerJob(workflow_id=workflow.workflow_id, schedule_id=schedule_id)
    db.session.add(workflows_apscheduler_job)

    # Get all jobs from the scheduler
    with get_scheduler() as scheduler:
        jobs = scheduler.get_jobs()
        enriched_tasks = enrich_with_workflow_id(jobs)

    assert len(enriched_tasks) == 1
    assert enriched_tasks[0].workflow_id == str(workflow.workflow_id)


def test_enrich_schedule_with_and_without_workflow_id(scheduler_with_jobs, clear_all_scheduler_jobs):
    clear_all_scheduler_jobs()

    workflow_name = "task_validate_products"
    workflow = get_workflow_by_name(workflow_name)

    schedule_id = f"{uuid4()}"
    scheduler_with_jobs(schedule_id=schedule_id)

    no_linker_schedule_id = f"{uuid4()}"
    scheduler_with_jobs(schedule_id=no_linker_schedule_id)

    workflows_apscheduler_job = WorkflowApschedulerJob(workflow_id=workflow.workflow_id, schedule_id=schedule_id)
    db.session.add(workflows_apscheduler_job)

    # Get all jobs from the scheduler
    with get_scheduler() as scheduler:
        jobs = scheduler.get_jobs()
        enriched_tasks = enrich_with_workflow_id(jobs)

    assert len(enriched_tasks) == 1
    assert enriched_tasks[0].workflow_id == str(workflow.workflow_id)


def test_enrich_all_schedule_with_workflow_id(scheduler_with_jobs, clear_all_scheduler_jobs):
    clear_all_scheduler_jobs()

    workflow_name = "task_validate_products"
    workflow = get_workflow_by_name(workflow_name)

    schedule_id = f"{uuid4()}"
    scheduler_with_jobs(schedule_id=schedule_id)
    workflows_apscheduler_job = WorkflowApschedulerJob(workflow_id=workflow.workflow_id, schedule_id=schedule_id)
    db.session.add(workflows_apscheduler_job)

    schedule_id = f"{uuid4()}"
    scheduler_with_jobs(schedule_id=schedule_id)
    workflows_apscheduler_job = WorkflowApschedulerJob(workflow_id=workflow.workflow_id, schedule_id=schedule_id)
    db.session.add(workflows_apscheduler_job)

    schedule_id = f"{uuid4()}"
    scheduler_with_jobs(schedule_id=schedule_id)
    workflows_apscheduler_job = WorkflowApschedulerJob(workflow_id=workflow.workflow_id, schedule_id=schedule_id)
    db.session.add(workflows_apscheduler_job)

    # Get all jobs from the scheduler
    with get_scheduler() as scheduler:
        jobs = scheduler.get_jobs()
        enriched_tasks = enrich_with_workflow_id(jobs)

    assert len(enriched_tasks) == 3
    assert enriched_tasks[0].workflow_id == str(workflow.workflow_id)
    assert enriched_tasks[1].workflow_id == str(workflow.workflow_id)
    assert enriched_tasks[2].workflow_id == str(workflow.workflow_id)


@patch("orchestrator.schedules.service.get_workflow_by_workflow_id", return_value=None)
def test_add_scheduled_task_raises_if_workflow_missing(mock_get_workflow):
    payload = APSchedulerJobCreate(
        name="Test",
        workflow_name="wf",
        workflow_id=uuid4(),
        trigger="interval",
        trigger_kwargs={"seconds": 10},
    )

    with patch("orchestrator.schedules.service.db.session.begin"):
        with pytest.raises(ValueError, match="Workflow with id"):
            _add_scheduled_task(payload, scheduler_connection=Mock())


def test_update_scheduled_task_raises_if_job_missing():
    payload = APSchedulerJobUpdate(
        schedule_id=uuid4(),
        name="Test",
        trigger="interval",
        trigger_kwargs={"seconds": 5},
    )

    scheduler = Mock()
    scheduler.get_job.return_value = None

    with pytest.raises(ValueError, match="does not exist"):
        _update_scheduled_task(payload, scheduler)


def test_update_scheduled_task_no_trigger_does_not_reschedule():
    payload = APSchedulerJobUpdate(
        schedule_id=uuid4(),
        name="NewName",
        trigger=None,
        trigger_kwargs=None,
    )

    mock_job = Mock()
    scheduler = Mock()
    scheduler.get_job.return_value = mock_job

    _update_scheduled_task(payload, scheduler)

    mock_job.reschedule.assert_not_called()
    mock_job.modify.assert_called_once_with(name="NewName")


@patch("orchestrator.schedules.service._delete_linker_entry")
def test_delete_scheduled_task_schedule_id_none(mock_delete_linker):
    payload = APSchedulerJobDelete(workflow_id=uuid4(), schedule_id=None)

    scheduler = Mock()

    _delete_scheduled_task(payload, scheduler)

    scheduler.remove_job.assert_called_once_with(job_id="None")
    mock_delete_linker.assert_called_once()


@patch("orchestrator.schedules.service.redis_connection")
def test_add_unique_scheduled_task_to_queue(mock_redis, scheduler_with_jobs):
    workflow_name = "task_validate_products"
    workflow = get_workflow_by_name(workflow_name)

    payload = APSchedulerJobCreate(
        name="Validate Workflows Scheduled Job",
        workflow_name=workflow_name,
        workflow_id=workflow.workflow_id,
        trigger="interval",
        trigger_kwargs={"hours": 5},
    )

    result = add_unique_scheduled_task_to_queue(payload)

    # Extract call args
    queue, bytes_arg = mock_redis.lpush.call_args[0]

    assert result
    assert queue == SCHEDULER_QUEUE
    assert isinstance(bytes_arg, bytes)
    assert b"workflow_name" in bytes_arg

    # Add job to the database
    schedule_id = f"{uuid4()}"
    scheduler_with_jobs(schedule_id=schedule_id)

    workflows_apscheduler_job = WorkflowApschedulerJob(workflow_id=workflow.workflow_id, schedule_id=schedule_id)
    db.session.add(workflows_apscheduler_job)

    # Try to add the same workflow again
    result = add_unique_scheduled_task_to_queue(payload)
    assert not result
