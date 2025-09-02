from uuid import uuid4

import pytest

from orchestrator.services.tasks import NEW_TASK, NEW_WORKFLOW, RESUME_TASK, RESUME_WORKFLOW
from orchestrator.workflow import ProcessStatus
from orchestrator.db import db, ProcessTable
from orchestrator.config.assignee import Assignee
from orchestrator.targets import Target
from datetime import datetime, timezone


@pytest.mark.celery
@pytest.mark.noresponses
def test_pytest_celery_all_tasks(celery_session_app, register_celery_tasks):
    """Test all registered celery tasks"""
    process_id = uuid4()

    # Test NEW_TASK
    result = register_celery_tasks[NEW_TASK].delay(process_id)
    assert result.get(timeout=5) == f"Started new process {process_id}"

    # Test NEW_WORKFLOW
    result = register_celery_tasks[NEW_WORKFLOW].delay(process_id)
    assert result.get(timeout=5) == f"Started new workflow {process_id}"

    # Test RESUME_TASK
    result = register_celery_tasks[RESUME_TASK].delay(process_id)
    assert result.get(timeout=5) == f"Resumed task {process_id}"

    # Test RESUME_WORKFLOW
    result = register_celery_tasks[RESUME_WORKFLOW].delay(process_id)
    assert result.get(timeout=5) == f"Resumed workflow {process_id}"


@pytest.mark.celery
@pytest.mark.noresponses
def test_test_orchestrator_celery_instance(celery_session_app):
    """Test that TestOrchestratorCelery properly initializes with test settings"""
    from test.unit_tests.conftest import TestOrchestratorCelery
    from orchestrator.settings import AppSettings

    # Create a test celery instance
    test_celery = TestOrchestratorCelery(
        "test-app",
        broker="redis://localhost:6379/0",
        backend="redis://localhost:6379/0"
    )

    # Verify the test settings were applied
    assert test_celery.conf.task_always_eager is True
    assert test_celery.conf.task_serializer == "orchestrator-json"

    # Verify the app settings were set to test mode
    test_settings = AppSettings()
    assert test_settings.TESTING is True

    # Create and run a test task
    @test_celery.task
    def test_task():
        return "test completed"

    result = test_task.delay()
    assert result.get(timeout=5) == "test completed"


@pytest.mark.celery
@pytest.mark.noresponses
def test_pytest_celery_start_task(celery_session_app, register_celery_tasks):
    process_id = str(uuid4())
    result = register_celery_tasks[NEW_TASK].delay(process_id)
    try:
        value = result.get(timeout=5, propagate=True)
        assert value == f"Started new process {process_id}"
    except Exception as e:
        print(f"Task state: {result.state}")
        print(f"Task info: {result.info}")
        raise


@pytest.mark.celery
@pytest.mark.noresponses
def test_pytest_celery_start_new_process(
    celery_session_app,
    celery_worker,
    register_celery_tasks,
    test_workflow_factory,
    cleanup_test_workflows,
    generic_subscription_1
):
    """Test starting a new process with celery worker"""
    # Create a test workflow that won't be removed
    workflow_name = f"Test Workflow {uuid4()}"
    workflow = test_workflow_factory(workflow_name)
    workflow.target = Target.SYSTEM
    workflow.deleted_at = None
    db.session.add(workflow)
    db.session.commit()
    db.session.refresh(workflow)

    # Create a process record
    process = ProcessTable(
        process_id=uuid4(),
        workflow_id=workflow.workflow_id,
        last_status=ProcessStatus.CREATED,
        is_task=False,
        assignee=Assignee.SYSTEM,
        started_at=datetime.now(timezone.utc)
    )
    db.session.add(process)
    db.session.commit()
    db.session.refresh(process)

    try:
        # Submit task to worker
        task = register_celery_tasks[NEW_WORKFLOW]
        result = task.apply_async(
            args=[str(process.process_id)],
            queue='new_tasks'
        )

        # Wait for result
        value = result.get(timeout=5, propagate=True)
        expected = f"Started new workflow {process.process_id}"
        assert str(value) == str(expected), f"Expected '{expected}', got '{value}'"

        # Verify task was processed
        assert result.state == 'SUCCESS'
        assert result.successful()

        # Verify process status
        db.session.refresh(process)
        assert process.last_status == ProcessStatus.CREATED
        assert process.assignee == Assignee.SYSTEM

    finally:
        # Cleanup
        db.session.delete(process)
        db.session.delete(workflow)
        db.session.commit()


@pytest.mark.celery
@pytest.mark.noresponses
def test_pytest_celery_resume_process(
    celery_session_app,
    celery_worker,
    register_celery_tasks,
    monkeypatch,
    test_workflow_factory
):
    """Test resume process using real workflow and process with pytest-celery"""
    from orchestrator.services.executors.celery import _celery_resume_process

    # Create a test workflow that won't be removed
    workflow_name = f"Test Workflow {uuid4()}"
    workflow = test_workflow_factory(workflow_name)
    workflow.target = Target.SYSTEM
    workflow.deleted_at = None  # Ensure workflow isn't marked as deleted
    db.session.add(workflow)
    db.session.commit()
    db.session.refresh(workflow)  # Ensure we have latest data

    # Create a process record with minimum required fields
    process = ProcessTable(
        process_id=uuid4(),
        workflow_id=workflow.workflow_id,
        last_status=ProcessStatus.FAILED,
        is_task=False,
        assignee=Assignee.SYSTEM,
        started_at=datetime.now(timezone.utc)
    )
    db.session.add(process)
    db.session.commit()
    db.session.refresh(process)  # Ensure we have latest data

    try:
        # Test the resume process
        process_id = _celery_resume_process(process)

        # Verify the process was resumed successfully
        assert process_id == process.process_id

        # Verify process status was updated
        db.session.refresh(process)
        assert process.last_status == ProcessStatus.RESUMED

        # Verify Celery task was called and completed
        task = register_celery_tasks[RESUME_WORKFLOW]
        result = task.apply_async(args=[str(process.process_id)], queue='resume_tasks')
        assert result.get(timeout=5) == f"Resumed workflow {process.process_id}"

    finally:
        # Cleanup
        db.session.delete(process)
        db.session.delete(workflow)  # Clean up the workflow as well
        db.session.commit()


