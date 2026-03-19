# test/integration_tests/locking/test_concurrent_locking.py
"""Concurrent locking integration tests.

Reproduces and validates PostgreSQL row-locking behavior with real Celery workers.
Requires PostgreSQL + Redis.

Run: uv run pytest test/integration_tests/locking/ -m locking -s
"""

import threading
import time

import pytest
import structlog
from celery import shared_task
from sqlalchemy import select

from orchestrator.db import ProcessTable, SubscriptionTable, db, transactional
from orchestrator.workflow import ProcessStatus
from test.integration_tests.locking.conftest import get_pg_lock_diagnostics, set_lock_timeouts_on_session

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Celery tasks — each creates its own database_scope() like production workers
# ---------------------------------------------------------------------------


@shared_task
def lock_process_row(process_id: str) -> str:
    """Lock a single ProcessTable row. No contention expected when each task gets its own row."""
    with db.database_scope():
        set_lock_timeouts_on_session()
        with transactional(db, logger):
            stmt = (
                select(ProcessTable)
                .where(ProcessTable.process_id == process_id)
                .with_for_update()
            )
            process = db.session.execute(stmt).scalar_one()
            process.last_status = ProcessStatus.RUNNING
            time.sleep(1)  # Hold lock to simulate work
    return f"locked {process_id}"


@shared_task
def lock_subscription_row(subscription_id: str) -> str:
    """Lock a SubscriptionTable row. Multiple tasks on the same row causes contention."""
    with db.database_scope():
        set_lock_timeouts_on_session()
        with transactional(db, logger):
            stmt = (
                select(SubscriptionTable)
                .where(SubscriptionTable.subscription_id == subscription_id)
                .with_for_update()
            )
            sub = db.session.execute(stmt).scalar_one()
            sub.description = f"locked by {threading.current_thread().name}"
            time.sleep(2)  # Hold lock longer to force contention
    return f"locked {subscription_id}"


# ---------------------------------------------------------------------------
# Helper: check idle-in-transaction AFTER tasks complete
# ---------------------------------------------------------------------------


def check_idle_in_transaction(monitoring_engine, context: str = ""):
    """Take a FRESH pg_stat_activity snapshot and check for idle-in-transaction.

    This is called AFTER all tasks have completed, with a brief delay to allow
    pool cleanup. This distinguishes between:
    - Expected idle-in-transaction DURING task execution (sleep inside txn)
    - Actual psycopg3 bug: idle-in-transaction AFTER task completion
    """
    # Brief delay to allow connection pool cleanup (pool_reset_on_return, checkin events)
    time.sleep(0.5)

    snapshot = get_pg_lock_diagnostics(monitoring_engine)
    idle_in_txn = [
        row for row in (snapshot or [])
        if row[1] == "idle in transaction"
        and "engine_settings" not in (row[4] or "")
    ]

    if idle_in_txn:
        logger.warning(
            "idle_in_transaction_detected_after_completion",
            context=context,
            sessions=idle_in_txn,
        )

    return idle_in_txn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.locking
def test_concurrent_process_locking_no_deadlock(
    database,  # noqa: F811 — ensures DB is initialized
    setup_process_rows,
    pg_monitor,
    monitoring_engine,
    celery_session_app,
    celery_session_worker,
):
    """3 workers lock their own ProcessTable row — no contention expected.

    All tasks should complete without lock_timeout errors.
    """
    process_ids = setup_process_rows

    # Dispatch 3 tasks concurrently
    results = [
        lock_process_row.apply_async(args=[pid]) for pid in process_ids
    ]

    # Wait for all results
    outputs = []
    for r in results:
        output = r.get(timeout=10)
        outputs.append(output)

    # All tasks completed
    assert len(outputs) == 3
    for pid in process_ids:
        assert any(pid in o for o in outputs)

    # FRESH snapshot after tasks complete — the real test
    idle_in_txn = check_idle_in_transaction(
        monitoring_engine, context="process_locking_no_deadlock"
    )
    assert idle_in_txn == [], (
        f"Sessions stuck in 'idle in transaction' AFTER task completion: {idle_in_txn}\n"
        f"This indicates psycopg3 connections are not properly cleaned up.\n"
        f"Monitor snapshots during execution: {len(pg_monitor['snapshots'])}"
    )


@pytest.mark.locking
def test_concurrent_subscription_lock_contention(
    database,  # noqa: F811
    setup_contended_subscription,
    pg_monitor,
    monitoring_engine,
    celery_session_app,
    celery_session_worker,
):
    """3 workers try to lock the SAME subscription row — tests serialized locking.

    Tasks should serialize (not deadlock). Lock timeout (10s) should not be exceeded.
    """
    sub_id = setup_contended_subscription

    # Dispatch 3 tasks for the same subscription
    results = [
        lock_subscription_row.apply_async(args=[sub_id]) for _ in range(3)
    ]

    # Wait for all results — worst case: 3 x 2s serialized + overhead
    outputs = []
    errors = []
    for r in results:
        try:
            output = r.get(timeout=30)
            outputs.append(output)
        except Exception as exc:
            errors.append(exc)

    # Build diagnostic message for failures
    diag_msg = ""
    if pg_monitor["snapshots"]:
        diag_msg += f"\nMonitor snapshots during execution: {len(pg_monitor['snapshots'])}"
    if pg_monitor["lock_chains"]:
        diag_msg += f"\nLock chains observed: {pg_monitor['lock_chains'][-1]}"

    # All 3 tasks should complete (serialized, not deadlocked)
    assert len(errors) == 0, (
        f"Tasks failed with errors: {errors}{diag_msg}"
    )
    assert len(outputs) == 3, (
        f"Expected 3 completed tasks, got {len(outputs)}{diag_msg}"
    )

    # FRESH snapshot after tasks complete — the real test
    idle_in_txn = check_idle_in_transaction(
        monitoring_engine, context="subscription_lock_contention"
    )
    assert idle_in_txn == [], (
        f"Sessions stuck in 'idle in transaction' AFTER task completion: {idle_in_txn}\n"
        f"This indicates psycopg3 connections are not properly cleaned up.{diag_msg}"
    )

    # Log lock chain info for debugging
    if pg_monitor["lock_chains"]:
        for chain in pg_monitor["lock_chains"]:
            logger.info("lock_contention_observed", chain=chain)
