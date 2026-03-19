# test/integration_tests/locking/conftest.py
"""Fixtures for concurrent locking integration tests.

These tests require real async Celery workers (not eager mode) to reproduce
lock contention scenarios. The celery_config here intentionally overrides the
session-scoped config in test/integration_tests/conftest.py.
"""

import os
import threading
from uuid import uuid4

import pytest
import redis
import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from orchestrator.db import ProcessTable, ProductTable, SubscriptionTable, WorkflowTable, db
from orchestrator.settings import app_settings
from orchestrator.targets import Target
from orchestrator.workflow import ProcessStatus
from test.unit_tests.conftest import (  # noqa: F401
    database,
    db_uri,
    fastapi_app,
    logger,
    run_migrations,
)

logger = structlog.get_logger(__name__)  # noqa: F811


@pytest.fixture(autouse=True)
def db_session():
    """Override the default db_session fixture.

    The default db_session wraps each test in a transaction with automatic rollback.
    For locking tests, we need committed data visible to Celery worker threads,
    so we skip the transaction wrapper and handle cleanup explicitly in fixtures.
    """
    yield


# ---------------------------------------------------------------------------
# Skip entire module if PostgreSQL or Redis are unreachable
# ---------------------------------------------------------------------------


_DEFAULT_DB_URI = "postgresql+psycopg://nwa:nwa@localhost/orchestrator-core-test"


def _pg_available() -> bool:
    """Check if PostgreSQL is available.

    Connects to the 'postgres' maintenance database (always exists) rather than
    the test database, which may not exist yet (created by the database fixture).
    """
    try:
        url = make_url(os.environ.get("DATABASE_URI", _DEFAULT_DB_URI))
        url = url.set(database="postgres")
        engine = create_engine(url, pool_size=1)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


def _redis_available() -> bool:
    """Check if Redis is available for Celery broker/backend."""
    try:
        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
        )
        client.ping()
        client.close()
        return True
    except redis.ConnectionError:
        return False


def pytest_collection_modifyitems(config, items):
    """Skip all locking tests early if PostgreSQL or Redis are unavailable.

    This runs before any fixtures, preventing the session-scoped `database`
    fixture from trying to connect to a non-existent PostgreSQL instance.
    """
    skip_reason = None
    if not _pg_available():
        skip_reason = "PostgreSQL is not available"
    elif not _redis_available():
        skip_reason = "Redis is not available"

    if skip_reason:
        skip_marker = pytest.mark.skip(reason=skip_reason)
        for item in items:
            if "locking" in item.keywords:
                item.add_marker(skip_marker)


# ---------------------------------------------------------------------------
# Celery configuration — overrides the parent conftest's session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def celery_config():

    return {
        "task_always_eager": False,
        "broker_url": os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        "result_backend": os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
        "worker_prefetch_multiplier": 1,
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
    }


@pytest.fixture(scope="session")
def celery_worker_parameters():
    return {
        "concurrency": 3,
        "perform_ping_check": False,
    }


@pytest.fixture(scope="session")
def celery_worker_pool():
    return "threads"


@pytest.fixture(scope="session")
def celery_includes():
    """Module containing the locking test tasks."""
    return ["test.integration_tests.locking.test_concurrent_locking"]


# ---------------------------------------------------------------------------
# Database engine with lock timeouts (safety nets for test hangs)
# ---------------------------------------------------------------------------


def set_lock_timeouts_on_session():
    """Set lock_timeout and idle_in_transaction_session_timeout on the current session.

    Called inside each Celery task's database_scope() to prevent hangs:
    - lock_timeout=10s — tasks sleep 1-2s, so 3 serialized = ~6s max
    - idle_in_transaction_session_timeout=15s — kill idle-in-txn sessions
    """
    db.session.execute(text("SET lock_timeout = '10s'"))
    db.session.execute(text("SET idle_in_transaction_session_timeout = '15s'"))


# ---------------------------------------------------------------------------
# Database fixtures — committed data (not inside test transaction rollback)
# ---------------------------------------------------------------------------


@pytest.fixture
def setup_process_rows():
    """Create a workflow + 3 process rows for the no-deadlock test.

    Uses db.database_scope() so data is committed and visible to worker threads.
    Cleanup via DELETE in teardown.
    """
    with db.database_scope():
        workflow = WorkflowTable(
            name=f"locking-test-{uuid4()}",
            description="Locking test workflow",
            target=Target.SYSTEM,
        )
        db.session.add(workflow)
        db.session.flush()

        process_ids = []
        for _ in range(3):
            pid = uuid4()
            process = ProcessTable(
                process_id=pid,
                workflow_id=workflow.workflow_id,
                last_status=ProcessStatus.CREATED,
                assignee=Target.SYSTEM,
            )
            db.session.add(process)
            process_ids.append(pid)

        db.session.commit()
        wf_id = workflow.workflow_id

    yield [str(pid) for pid in process_ids]

    # Cleanup
    with db.database_scope():
        db.session.execute(
            text("DELETE FROM processes WHERE workflow_id = :wf_id"),
            {"wf_id": str(wf_id)},
        )
        db.session.execute(
            text("DELETE FROM workflows WHERE workflow_id = :wf_id"),
            {"wf_id": str(wf_id)},
        )
        db.session.commit()


@pytest.fixture
def setup_contended_subscription():
    """Create a product + 1 subscription row for the contention test.

    Uses db.database_scope() so data is committed and visible to worker threads.
    Cleanup via DELETE in teardown.
    """
    with db.database_scope():
        product = ProductTable(
            name=f"locking-test-product-{uuid4()}",
            description="Locking test product",
            product_type="LockTest",
            tag="LOCK",
            status="active",
        )
        db.session.add(product)
        db.session.flush()

        sub_id = uuid4()
        subscription = SubscriptionTable(
            subscription_id=sub_id,
            description="locking test subscription",
            status="active",
            product_id=product.product_id,
            customer_id=str(uuid4()),
            insync=True,
        )
        db.session.add(subscription)
        db.session.commit()
        prod_id = product.product_id

    yield str(sub_id)

    # Cleanup
    with db.database_scope():
        db.session.execute(
            text("DELETE FROM subscriptions WHERE subscription_id = :sid"),
            {"sid": str(sub_id)},
        )
        db.session.execute(
            text("DELETE FROM products WHERE product_id = :pid"),
            {"pid": str(prod_id)},
        )
        db.session.commit()


# ---------------------------------------------------------------------------
# pg_stat_activity monitoring
# ---------------------------------------------------------------------------


@pytest.fixture
def monitoring_engine():
    """Separate SQLAlchemy engine for pg_stat_activity queries (pool_size=1).

    Adds lock_timeout and idle_in_transaction_session_timeout as safety nets
    so stuck locks cause test failures instead of indefinite hangs.
    """
    uri = os.environ.get("DATABASE_URI", _DEFAULT_DB_URI)
    engine = create_engine(
        uri,
        pool_size=1,
        pool_pre_ping=True,
        connect_args={
            "options": "-c timezone=UTC -c lock_timeout=10000 -c idle_in_transaction_session_timeout=15000"
        },
    )
    yield engine
    engine.dispose()


def get_pg_lock_diagnostics(monitoring_engine):
    """Query pg_stat_activity outside the SQLAlchemy pool."""
    raw_conn = monitoring_engine.raw_connection()
    try:
        with raw_conn.cursor() as cur:
            cur.execute(
                """
                SELECT pid, state, wait_event_type, wait_event,
                       query, xact_start, state_change
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND pid != pg_backend_pid()
                  AND state != 'idle'
                ORDER BY xact_start
                """
            )
            return cur.fetchall()
    finally:
        raw_conn.close()


def get_lock_chain(monitoring_engine):
    """Query pg_locks to find blocking relationships."""
    raw_conn = monitoring_engine.raw_connection()
    try:
        with raw_conn.cursor() as cur:
            cur.execute(
                """
                SELECT blocked.pid    AS blocked_pid,
                       blocked.query  AS blocked_query,
                       blocking.pid   AS blocking_pid,
                       blocking.query AS blocking_query,
                       blocking.state AS blocking_state
                FROM pg_locks blocked_locks
                         JOIN pg_stat_activity blocked ON blocked.pid = blocked_locks.pid
                         JOIN pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
                    AND blocking_locks.relation = blocked_locks.relation
                    AND blocking_locks.pid != blocked_locks.pid
                    AND blocking_locks.granted
                         JOIN pg_stat_activity blocking ON blocking.pid = blocking_locks.pid
                WHERE NOT blocked_locks.granted
                """
            )
            return cur.fetchall()
    finally:
        raw_conn.close()


@pytest.fixture
def pg_monitor(monitoring_engine):
    """Background pg_stat_activity poller. Collects snapshots every 0.5s."""
    snapshots = []
    lock_chains = []
    stop_event = threading.Event()
    errors = []

    def _poll():
        while not stop_event.is_set():
            try:
                snap = get_pg_lock_diagnostics(monitoring_engine)
                if snap:
                    snapshots.append(snap)
                chain = get_lock_chain(monitoring_engine)
                if chain:
                    lock_chains.append(chain)
            except Exception as exc:
                errors.append(str(exc))
                logger.warning("pg_monitor error", error=str(exc))
            stop_event.wait(0.5)

    thread = threading.Thread(target=_poll, daemon=True, name="pg_monitor")
    thread.start()

    yield {"snapshots": snapshots, "lock_chains": lock_chains, "errors": errors}

    stop_event.set()
    thread.join(timeout=5)

    # Log all collected diagnostics
    for i, snap in enumerate(snapshots):
        logger.info("pg_stat_activity snapshot", index=i, rows=snap)
    for i, chain in enumerate(lock_chains):
        logger.info("lock_chain snapshot", index=i, chains=chain)
    if errors:
        logger.warning("pg_monitor errors", errors=errors)
