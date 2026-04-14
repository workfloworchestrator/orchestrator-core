"""Tests for orchestrator/services/tasks.py.

Covers get_celery_task, register_custom_serializer, initialise_celery (including transactional wrapping),
and CeleryJobWorkerStatus.
"""

from contextlib import contextmanager
from unittest.mock import ANY, MagicMock, patch
from uuid import uuid4

import pytest

import orchestrator.services.tasks as tasks_module
from orchestrator.services.tasks import (
    NEW_TASK,
    NEW_WORKFLOW,
    RESUME_TASK,
    RESUME_WORKFLOW,
    CeleryJobWorkerStatus,
    get_celery_task,
    initialise_celery,
    register_custom_serializer,
)


@pytest.fixture(autouse=True)
def reset_celery_global():
    """Restore the _celery global to its original value after each test.

    initialise_celery() sets a module-level global; without cleanup, test
    ordering can cause 'You can only initialise Celery once' failures.
    """
    original = tasks_module._celery
    tasks_module._celery = None
    yield
    tasks_module._celery = original


def _make_capturing_celery():
    """Return a (mock_celery, captured) pair.

    mock_celery.task acts as a real decorator factory instead of a MagicMock,
    so that @celery_task(name=...) stores the *original* function in `captured`
    rather than wrapping it in another MagicMock.  This lets tests invoke the
    inner start_process / resume_process closures directly.
    """
    captured: dict = {}

    def task_factory(**kwargs):
        def decorator(fn):
            captured[kwargs["name"]] = fn
            return fn

        return decorator

    celery = MagicMock()
    celery.task = task_factory
    return celery, captured


@contextmanager
def _noop_transactional(db, log):  # type: ignore[no-untyped-def]
    yield


# ---------------------------------------------------------------------------
# get_celery_task
# ---------------------------------------------------------------------------


def test_get_celery_task_returns_signature_when_initialized():
    mock_celery = MagicMock()
    tasks_module._celery = mock_celery

    result = get_celery_task("tasks.new_task")

    mock_celery.signature.assert_called_once_with("tasks.new_task")
    assert result is mock_celery.signature.return_value


def test_get_celery_task_raises_when_not_initialized():
    tasks_module._celery = None

    with pytest.raises(AssertionError, match="Celery has not been initialised yet"):
        get_celery_task("tasks.new_task")


# ---------------------------------------------------------------------------
# register_custom_serializer
# ---------------------------------------------------------------------------


def test_register_custom_serializer_registers_orchestrator_json():
    with patch("orchestrator.services.tasks.registry") as mock_registry:
        register_custom_serializer()

    mock_registry.register.assert_called_once_with("orchestrator-json", ANY, ANY, "application/json", "utf-8")


# ---------------------------------------------------------------------------
# initialise_celery
# ---------------------------------------------------------------------------


def test_initialise_celery_raises_on_double_init():
    tasks_module._celery = MagicMock()  # simulate already initialised

    with pytest.raises(AssertionError, match="only initialise Celery once"):
        initialise_celery(MagicMock())


def test_initialise_celery_sets_task_routes():
    celery, _ = _make_capturing_celery()

    with patch("orchestrator.services.tasks.register_custom_serializer"):
        initialise_celery(celery)

    assert celery.conf.task_routes == {
        NEW_TASK: {"queue": "new_tasks"},
        NEW_WORKFLOW: {"queue": "new_workflows"},
        RESUME_TASK: {"queue": "resume_tasks"},
        RESUME_WORKFLOW: {"queue": "resume_workflows"},
    }


def test_initialise_celery_registers_four_named_tasks():
    celery, captured = _make_capturing_celery()

    with patch("orchestrator.services.tasks.register_custom_serializer"):
        initialise_celery(celery)

    assert set(captured.keys()) == {NEW_TASK, NEW_WORKFLOW, RESUME_TASK, RESUME_WORKFLOW}


# ---------------------------------------------------------------------------
# start_process (inner closure) — called by new_task / new_workflow
# ---------------------------------------------------------------------------


@pytest.fixture
def celery_start_fn():
    """Return the inner start_process closure via the capturing celery pattern."""
    celery, captured = _make_capturing_celery()
    with patch("orchestrator.services.tasks.register_custom_serializer"):
        initialise_celery(celery)
    return captured[NEW_TASK]  # new_task delegates to start_process


def test_start_process_wraps_db_reads_in_transactional(celery_start_fn):
    """start_process must call transactional(db, ...) to prevent idle-in-transaction on psycopg3."""
    process_id = uuid4()
    mock_pstat = MagicMock()

    with (
        patch("orchestrator.services.tasks.transactional", side_effect=_noop_transactional) as mock_tx,
        patch("orchestrator.services.tasks._get_process", return_value=MagicMock()),
        patch("orchestrator.services.tasks.load_process", return_value=mock_pstat),
        patch("orchestrator.services.tasks.ensure_correct_process_status"),
        patch("orchestrator.services.tasks.thread_start_process"),
    ):
        celery_start_fn(process_id, "user")

    mock_tx.assert_called_once_with(tasks_module.db, ANY)


def test_start_process_returns_process_id_on_success(celery_start_fn):
    process_id = uuid4()
    mock_pstat = MagicMock()

    with (
        patch("orchestrator.services.tasks.transactional", side_effect=_noop_transactional),
        patch("orchestrator.services.tasks._get_process", return_value=MagicMock()),
        patch("orchestrator.services.tasks.load_process", return_value=mock_pstat),
        patch("orchestrator.services.tasks.ensure_correct_process_status"),
        patch("orchestrator.services.tasks.thread_start_process"),
    ):
        result = celery_start_fn(process_id, "user")

    assert result == process_id


@pytest.mark.parametrize("failing_fn", ["_get_process", "load_process", "thread_start_process"])
def test_start_process_returns_none_on_exception(celery_start_fn, failing_fn):
    process_id = uuid4()

    patches = {
        "orchestrator.services.tasks.transactional": patch(
            "orchestrator.services.tasks.transactional", side_effect=_noop_transactional
        ),
        "orchestrator.services.tasks._get_process": patch(
            "orchestrator.services.tasks._get_process", return_value=MagicMock()
        ),
        "orchestrator.services.tasks.load_process": patch(
            "orchestrator.services.tasks.load_process", return_value=MagicMock()
        ),
        "orchestrator.services.tasks.ensure_correct_process_status": patch(
            "orchestrator.services.tasks.ensure_correct_process_status"
        ),
        "orchestrator.services.tasks.thread_start_process": patch("orchestrator.services.tasks.thread_start_process"),
    }

    with (
        patches["orchestrator.services.tasks.transactional"],
        patches["orchestrator.services.tasks._get_process"] as m_get,
        patches["orchestrator.services.tasks.load_process"] as m_load,
        patches["orchestrator.services.tasks.ensure_correct_process_status"],
        patches["orchestrator.services.tasks.thread_start_process"] as m_thread,
    ):
        target = {"_get_process": m_get, "load_process": m_load, "thread_start_process": m_thread}[failing_fn]
        target.side_effect = RuntimeError("boom")
        result = celery_start_fn(process_id, "user")

    assert result is None


# ---------------------------------------------------------------------------
# resume_process (inner closure) — called by resume_task / resume_workflow
# ---------------------------------------------------------------------------


@pytest.fixture
def celery_resume_fn():
    """Return the inner resume_process closure via the capturing celery pattern."""
    celery, captured = _make_capturing_celery()
    with patch("orchestrator.services.tasks.register_custom_serializer"):
        initialise_celery(celery)
    return captured[RESUME_TASK]  # resume_task delegates to resume_process


def test_resume_process_wraps_db_reads_in_transactional(celery_resume_fn):
    """resume_process must call transactional(db, ...) to prevent idle-in-transaction on psycopg3."""
    process_id = uuid4()

    with (
        patch("orchestrator.services.tasks.transactional", side_effect=_noop_transactional) as mock_tx,
        patch("orchestrator.services.tasks._get_process", return_value=MagicMock()),
        patch("orchestrator.services.tasks.ensure_correct_process_status"),
        patch("orchestrator.services.tasks.thread_resume_process"),
    ):
        celery_resume_fn(process_id, "user")

    mock_tx.assert_called_once_with(tasks_module.db, ANY)


def test_resume_process_returns_process_id_on_success(celery_resume_fn):
    process_id = uuid4()

    with (
        patch("orchestrator.services.tasks.transactional", side_effect=_noop_transactional),
        patch("orchestrator.services.tasks._get_process", return_value=MagicMock()),
        patch("orchestrator.services.tasks.ensure_correct_process_status"),
        patch("orchestrator.services.tasks.thread_resume_process"),
    ):
        result = celery_resume_fn(process_id, "user")

    assert result == process_id


@pytest.mark.parametrize("failing_fn", ["_get_process", "thread_resume_process"])
def test_resume_process_returns_none_on_exception(celery_resume_fn, failing_fn):
    process_id = uuid4()

    with (
        patch("orchestrator.services.tasks.transactional", side_effect=_noop_transactional),
        patch("orchestrator.services.tasks._get_process", return_value=MagicMock()) as m_get,
        patch("orchestrator.services.tasks.ensure_correct_process_status"),
        patch("orchestrator.services.tasks.thread_resume_process") as m_thread,
    ):
        target = {"_get_process": m_get, "thread_resume_process": m_thread}[failing_fn]
        target.side_effect = RuntimeError("boom")
        result = celery_resume_fn(process_id, "user")

    assert result is None


# ---------------------------------------------------------------------------
# CeleryJobWorkerStatus (existing fixture kept below)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_celery():
    """Create a mock Celery instance."""
    return MagicMock()


def test_celery_job_worker_status_handles_none_from_inspection_api(mock_celery):
    """Test that CeleryJobWorkerStatus handles None returns from Celery inspection API.

    This can happen with prefork worker pool when workers don't respond within timeout.
    Fixes issue #1455.
    """
    # Mock the inspection API to return None (as happens with prefork worker pool)
    mock_inspect = MagicMock()
    mock_inspect.stats.return_value = None
    mock_inspect.scheduled.return_value = None
    mock_inspect.reserved.return_value = None
    mock_inspect.active.return_value = None

    mock_celery.control.inspect.return_value = mock_inspect

    # Initialize celery so _celery global is set
    with patch("orchestrator.services.tasks._celery", mock_celery):
        # Should not raise TypeError: object of type 'NoneType' has no len()
        status = CeleryJobWorkerStatus()

        # Verify it handles None gracefully with appropriate defaults
        assert status.number_of_workers_online == 0
        assert status.number_of_queued_jobs == 0
        assert status.number_of_running_jobs == 0
        assert status.executor_type == "celery"


def test_celery_job_worker_status_with_valid_inspection_data(mock_celery):
    """Test that CeleryJobWorkerStatus correctly processes valid inspection data."""
    # Mock the inspection API with valid data
    mock_inspect = MagicMock()
    mock_inspect.stats.return_value = {
        "worker1@host": {"total": {}},
        "worker2@host": {"total": {}},
    }
    mock_inspect.scheduled.return_value = {
        "worker1@host": [{"id": "task1"}, {"id": "task2"}],
    }
    mock_inspect.reserved.return_value = {
        "worker1@host": [{"id": "task3"}],
    }
    mock_inspect.active.return_value = {
        "worker1@host": [{"id": "task4"}, {"id": "task5"}],
        "worker2@host": [{"id": "task6"}],
    }

    mock_celery.control.inspect.return_value = mock_inspect

    with patch("orchestrator.services.tasks._celery", mock_celery):
        status = CeleryJobWorkerStatus()

        assert status.number_of_workers_online == 2
        assert status.number_of_queued_jobs == 3  # 2 scheduled + 1 reserved
        assert status.number_of_running_jobs == 3  # 2 active on worker1 + 1 on worker2
        assert status.executor_type == "celery"


def test_celery_job_worker_status_with_mixed_none_and_valid_data(mock_celery):
    """Test that CeleryJobWorkerStatus handles mix of None and valid data."""
    # Mock the inspection API with some None and some valid data
    mock_inspect = MagicMock()
    mock_inspect.stats.return_value = {"worker1@host": {"total": {}}}
    mock_inspect.scheduled.return_value = None  # Returns None
    mock_inspect.reserved.return_value = {"worker1@host": [{"id": "task1"}]}
    mock_inspect.active.return_value = None  # Returns None

    mock_celery.control.inspect.return_value = mock_inspect

    with patch("orchestrator.services.tasks._celery", mock_celery):
        status = CeleryJobWorkerStatus()

        assert status.number_of_workers_online == 1
        assert status.number_of_queued_jobs == 1  # 0 scheduled + 1 reserved
        assert status.number_of_running_jobs == 0
        assert status.executor_type == "celery"


def test_celery_job_worker_status_with_empty_dicts(mock_celery):
    """Test that CeleryJobWorkerStatus handles empty dict returns."""
    # Mock the inspection API with empty dicts
    mock_inspect = MagicMock()
    mock_inspect.stats.return_value = {}
    mock_inspect.scheduled.return_value = {}
    mock_inspect.reserved.return_value = {}
    mock_inspect.active.return_value = {}

    mock_celery.control.inspect.return_value = mock_inspect

    with patch("orchestrator.services.tasks._celery", mock_celery):
        status = CeleryJobWorkerStatus()

        assert status.number_of_workers_online == 0
        assert status.number_of_queued_jobs == 0
        assert status.number_of_running_jobs == 0
        assert status.executor_type == "celery"


def test_celery_job_worker_status_without_celery_initialized():
    """Test that CeleryJobWorkerStatus handles case when Celery is not initialized."""
    with patch("orchestrator.services.tasks._celery", None):
        with patch("orchestrator.services.tasks.logger") as mock_logger:
            # Should not crash, just log error
            status = CeleryJobWorkerStatus()

            # Verify it creates the object but with default executor_type
            assert status.executor_type == "celery"

            # Verify error was logged
            mock_logger.error.assert_called_once_with("Can't create CeleryJobStatistics. Celery is not initialised.")
