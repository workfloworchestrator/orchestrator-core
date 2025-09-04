"""Integration tests for Celery functionality."""

from uuid import uuid4

import pytest

from orchestrator.db import db
from orchestrator.services.tasks import NEW_TASK, NEW_WORKFLOW, RESUME_TASK, RESUME_WORKFLOW
from orchestrator.targets import Target
from orchestrator.workflow import ProcessStatus
from test.integration_test.conftest import TestOrchestratorCelery


@pytest.fixture(scope="module")
def init_celery_app(celery_session_app):
    """Initialize Celery application for testing.

    Sets up custom serialization and initializes the Celery app.

    Args:
        celery_session_app: The Celery application instance from pytest-celery

    Returns:
        Celery: The configured Celery application
    """
    from orchestrator.services.tasks import initialise_celery

    initialise_celery(celery_session_app)
    return celery_session_app


@pytest.fixture
def celery_worker_setup(celery_worker):
    """Worker fixture that matches the scope of celery_worker."""
    try:
        yield celery_worker
    finally:
        # Ensure worker connections are closed
        if hasattr(celery_worker, "app"):
            celery_worker.app.control.purge()
            if hasattr(celery_worker.app, "close"):
                celery_worker.app.close()
            # Force close any remaining db connections from the worker
            if hasattr(db, "wrapped_database"):
                if hasattr(db.wrapped_database, "engine"):
                    db.wrapped_database.engine.dispose()
                if hasattr(db.wrapped_database, "scoped_session"):
                    db.wrapped_database.scoped_session.remove()


@pytest.mark.celery
@pytest.mark.noresponses
def test_pytest_celery_all_tasks(init_celery_app, register_celery_tasks):
    """Test all registered celery tasks."""
    process_id = str(uuid4())
    tasks = [
        (NEW_TASK, "Started new process"),
        (NEW_WORKFLOW, "Started new workflow"),
        (RESUME_TASK, "Resumed task"),
        (RESUME_WORKFLOW, "Resumed workflow"),
    ]

    for task_name, expected_prefix in tasks:
        result = register_celery_tasks[task_name].delay(process_id)
        assert result.get(timeout=5) == f"{expected_prefix} {process_id}"


@pytest.mark.celery
@pytest.mark.noresponses
def test_orchestrator_celery_instance(init_celery_app):
    """Test TestOrchestratorCelery initialization."""
    from orchestrator.settings import AppSettings

    # Create a test celery instance
    test_celery = TestOrchestratorCelery("test-app", broker="memory://", backend="cache+memory://")

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
@pytest.mark.parametrize("setup_test_process", [ProcessStatus.CREATED], indirect=True)
def test_pytest_celery_start_new_process(
    init_celery_app, celery_worker_setup, register_celery_tasks, setup_test_process
):
    """Test starting a new process with celery worker."""
    workflow, process = setup_test_process

    # Submit task to worker
    task = register_celery_tasks[NEW_WORKFLOW]
    result = task.apply_async(args=[str(process.process_id)], queue="new_workflows")

    # Wait for result and verify
    value = result.get(timeout=5, propagate=True)
    expected = f"Started new workflow {process.process_id}"
    assert str(value) == str(expected), f"Expected '{expected}', got '{value}'"

    # Verify task was processed successfully
    assert result.state == "SUCCESS"
    assert result.successful()

    # Verify process status
    db.session.refresh(process)
    assert process.last_status == ProcessStatus.CREATED
    assert process.assignee == Target.SYSTEM


@pytest.mark.celery
@pytest.mark.noresponses
@pytest.mark.parametrize("setup_test_process", [ProcessStatus.FAILED], indirect=True)
def test_pytest_celery_resume_process(init_celery_app, celery_worker_setup, register_celery_tasks, setup_test_process):
    """Test resume process workflow."""
    from orchestrator.services.executors.celery import _celery_resume_process

    workflow, process = setup_test_process

    # Resume process and verify
    returned_process_id = _celery_resume_process(process)
    assert returned_process_id == process.process_id

    # Verify process status was updated
    db.session.refresh(process)
    assert process.last_status == ProcessStatus.RESUMED

    # Verify task execution
    result = register_celery_tasks[RESUME_WORKFLOW].apply_async(
        args=[str(process.process_id)], queue="resume_workflows"
    )
    assert result.get(timeout=5) == f"Resumed workflow {process.process_id}"
