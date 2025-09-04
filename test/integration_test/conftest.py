"""Integration test configuration."""

import os
from contextlib import contextmanager
from uuid import uuid4

import pytest
import redis
import structlog
from celery import Celery
from sqlalchemy import select

from orchestrator.db import ProcessTable, WorkflowTable, db
from orchestrator.services.tasks import (
    NEW_TASK,
    NEW_WORKFLOW,
    RESUME_TASK,
    RESUME_WORKFLOW,
    initialise_celery,
    register_custom_serializer,
)
from orchestrator.settings import AppSettings
from orchestrator.targets import Target
from orchestrator.workflow import ProcessStatus
from test.unit_tests.conftest import (  # noqa: F401,E402
    database,
    db_session,
    # Database fixtures
    db_uri,
    # Application fixtures
    fastapi_app,
    # Utils
    logger,
    # Base workflow fixtures
    run_migrations,
)

# Configure structlog to handle exceptions properly in tests
logger = structlog.get_logger(__name__)  # noqa: F811

# Singleton Redis connection pool
_redis_pool = None


def get_redis_connection():
    """Get Redis connection from pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True,
            max_connections=5,  # Limit connections for testing
        )
    return redis.Redis(connection_pool=_redis_pool)


@contextmanager
def redis_client():
    """Context manager for Redis connections."""
    client = get_redis_connection()
    try:
        yield client
    finally:
        client.close()


def validate_redis_connection():
    """Validate Redis connection is available."""
    try:
        with redis_client() as client:
            return client.ping()
    except redis.ConnectionError:
        return False


class TestOrchestratorCelery(Celery):
    """Test-specific Celery application class with pre-configured settings."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set test configuration during initialization
        self.conf.update(
            task_always_eager=True,
            task_eager_propagates=True,
            task_serializer="orchestrator-json",
            accept_content=["orchestrator-json", "json"],
            result_serializer="json",
            task_track_started=True,
        )

    def on_init(self) -> None:
        """Initialize test settings and create mock OrchestratorCore."""
        test_settings = AppSettings()
        test_settings.TESTING = True

        class MockOrchestratorCore:
            def __init__(self, base_settings):
                self.settings = base_settings
                self.broadcast_thread = type("DummyThread", (), {"start": lambda: None, "stop": lambda: None})()

        app = MockOrchestratorCore(base_settings=test_settings)  # noqa:  F841


@pytest.fixture
def setup_test_process(request, db_session):  # noqa: F811
    """Create test workflow and process for celery tests.

    Args:
        request: The pytest request object, may contain 'param' for status
        db_session: Database session fixture

    Returns:
        tuple: (workflow, process) The created test workflow and process
    """

    def _create_process(status=ProcessStatus.CREATED):
        workflow = WorkflowTable(
            name=f"Test Workflow {uuid4()}", description="Test workflow for celery", target=Target.SYSTEM
        )
        db.session.add(workflow)
        db.session.commit()

        process = ProcessTable(
            workflow_id=workflow.workflow_id, last_status=status, assignee=Target.SYSTEM, process_id=uuid4()
        )
        db.session.add(process)
        db.session.commit()

        return workflow, process

    if hasattr(request, "param"):
        return _create_process(request.param)
    return _create_process()


@pytest.fixture
def setup_base_workflows(db_session):  # noqa: F811
    """Create base workflows needed for tests.

    Returns:
        WorkflowTable: The created or existing modify_note workflow
    """

    # Check if workflow exists
    existing = db.session.scalar(select(WorkflowTable).where(WorkflowTable.name == "modify_note"))

    if not existing:
        workflow = WorkflowTable(name="modify_note", description="Test workflow for modify_note", target=Target.SYSTEM)
        db.session.add(workflow)
        db.session.commit()
        return workflow

    return existing


@pytest.fixture(scope="session")
def celery_config():
    """Optimized Celery configuration for testing."""
    if not validate_redis_connection():
        pytest.skip("Redis is not available")

    return {
        "broker_url": os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        "result_backend": os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
        "broker_connection_pool_limit": 2,
        "result_backend_connection_pool_limit": 2,
        "task_always_eager": True,  # Run tasks synchronously for testing
        "task_eager_propagates": True,
        "task_serializer": "orchestrator-json",
        "result_serializer": "json",
        "accept_content": ["orchestrator-json", "json"],
        "task_routes": {
            NEW_TASK: {"queue": "test_tasks"},
            NEW_WORKFLOW: {"queue": "test_workflows"},
            RESUME_TASK: {"queue": "test_tasks"},
            RESUME_WORKFLOW: {"queue": "test_workflows"},
        },
        "worker_prefetch_multiplier": 1,
        "worker_max_tasks_per_child": 10,  # Increased for better performance
        "task_acks_late": False,  # Disable late acks for testing
        "broker_connection_retry": False,  # Disable retries for faster failures
        "broker_connection_timeout": 2,  # Reduced timeout
        "result_expires": 60,  # Reduced expiry time for test results
        "broker_heartbeat": 0,
        "worker_send_task_events": False,
        "event_queue_expires": 10,
        "worker_disable_rate_limits": True,
    }


@pytest.fixture(scope="session")
def celery_worker_parameters():
    """Optimized worker configuration for testing."""
    return {
        "perform_ping_check": False,
        "queues": ["test_tasks", "test_workflows"],
        "concurrency": 1,
        "pool": "solo",
        "without_heartbeat": True,
        "without_mingle": True,
        "without_gossip": True,
        "shutdown_timeout": 0,
    }


@pytest.fixture(scope="session")
def register_celery_tasks(celery_session_app):
    """Register test tasks with the Celery application."""
    tasks = {}

    @celery_session_app.task(name=NEW_TASK)  # type: ignore[misc]
    def new_task(process_id: str, user: str = "test") -> str:
        return f"Started new process {process_id}"

    tasks[NEW_TASK] = new_task

    @celery_session_app.task(name=NEW_WORKFLOW)  # type: ignore[misc]
    def new_workflow(process_id: str, user: str = "test") -> str:
        return f"Started new workflow {process_id}"

    tasks[NEW_WORKFLOW] = new_workflow

    @celery_session_app.task(name=RESUME_TASK)  # type: ignore[misc]
    def resume_task(process_id: str, user: str = "test") -> str:
        return f"Resumed task {process_id}"

    tasks[RESUME_TASK] = resume_task

    @celery_session_app.task(name=RESUME_WORKFLOW)  # type: ignore[misc]
    def resume_workflow(process_id: str, user: str = "test") -> str:
        if process_id is None:
            raise ValueError("process_id cannot be None")
        return f"Resumed workflow {process_id}"

    tasks[RESUME_WORKFLOW] = resume_workflow

    return tasks


@pytest.fixture(scope="session")
def celery_includes():
    """Specify modules to import for task registration."""
    return ["orchestrator.services.tasks"]


@pytest.fixture
def celery_timeout():
    """Consistent timeout value for all tests."""
    return 10


@pytest.fixture(autouse=True)
def setup_test_celery(celery_session_app, monkeypatch):
    """Setup and teardown for Celery tests."""
    # Reset Celery app
    monkeypatch.setattr("orchestrator.services.tasks._celery", None)

    # Initialize Celery
    register_custom_serializer()
    initialise_celery(celery_session_app)

    yield

    # Cleanup
    if _redis_pool:
        with redis_client() as client:
            client.flushdb()  # Clean test data
        _redis_pool.disconnect()  # Close all connections
