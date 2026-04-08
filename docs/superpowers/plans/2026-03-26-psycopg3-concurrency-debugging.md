# Psycopg3 Concurrency Debugging & Timeouts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add PostgreSQL lock/idle timeouts and write concurrency tests that reproduce and diagnose the worker lock contention issue with psycopg3.

**Architecture:** Two changes: (1) add `lock_timeout` and `idle_in_transaction_session_timeout` to the existing `ENGINE_ARGUMENTS` connect_args, (2) a new test file with a parameterized concurrency test that runs 3 threads doing `SELECT ... FOR UPDATE` on the same row, with and without `ClientCursor`, plus a `pg_stat_activity` helper to detect idle-in-transaction sessions.

**Tech Stack:** Python, SQLAlchemy, psycopg3, pytest, threading

---

### Task 1: Add PostgreSQL timeouts to ENGINE_ARGUMENTS

**Files:**
- Modify: `orchestrator/db/database.py:169`

- [ ] **Step 1: Modify the connect_args options string**

In `orchestrator/db/database.py`, change line 169 from:

```python
    "connect_args": {"connect_timeout": 10, "options": "-c timezone=UTC"},
```

to:

```python
    "connect_args": {
        "connect_timeout": 10,
        "options": "-c timezone=UTC -c lock_timeout=30000 -c idle_in_transaction_session_timeout=60000",
    },
```

- [ ] **Step 2: Run existing tests to verify no regressions**

Run: `uv run pytest test/unit_tests/test_db.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add orchestrator/db/database.py
git commit -m "Add lock_timeout and idle_in_transaction_session_timeout to ENGINE_ARGUMENTS

Adds 30s lock_timeout to prevent queries waiting indefinitely for locks,
and 60s idle_in_transaction_session_timeout as a safety net to kill
sessions stuck in idle-in-transaction state."
```

---

### Task 2: Write pg_stat_activity helper and concurrency test scaffold

**Files:**
- Create: `test/unit_tests/test_psycopg3_concurrency.py`

- [ ] **Step 1: Create test file with pg_stat_activity helper and imports**

Create `test/unit_tests/test_psycopg3_concurrency.py`:

```python
import threading
import time
from uuid import uuid4

import pytest
from psycopg import ClientCursor
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from orchestrator.db import ProcessTable, WorkflowTable, db
from orchestrator.db.database import ENGINE_ARGUMENTS, WrappedSession
from orchestrator.targets import Target
from orchestrator.workflow import ProcessStatus


def get_idle_in_transaction_count(engine) -> int:
    """Query pg_stat_activity for idle-in-transaction sessions on this database."""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE state = 'idle in transaction' "
                "AND datname = current_database() "
                "AND pid <> pg_backend_pid()"
            )
        )
        return result.scalar()
```

- [ ] **Step 2: Commit scaffold**

```bash
git add test/unit_tests/test_psycopg3_concurrency.py
git commit -m "Add psycopg3 concurrency test scaffold with pg_stat_activity helper"
```

---

### Task 3: Write the concurrent FOR UPDATE test

**Files:**
- Modify: `test/unit_tests/test_psycopg3_concurrency.py`

- [ ] **Step 1: Write the parameterized concurrency test**

Append to `test/unit_tests/test_psycopg3_concurrency.py`:

```python
def _make_engine(db_url: str, use_client_cursor: bool):
    """Create an engine, optionally with ClientCursor for client-side parameter binding."""
    engine_args = {**ENGINE_ARGUMENTS}
    if use_client_cursor:
        engine_args["connect_args"] = {
            **ENGINE_ARGUMENTS["connect_args"],
            "cursor_factory": ClientCursor,
        }
    return create_engine(db_url, **engine_args)


def _worker_lock_and_update(
    db_url: str,
    process_id,
    worker_id: int,
    barrier: threading.Barrier,
    results: dict,
    use_client_cursor: bool,
):
    """Worker thread: open a session, lock the ProcessTable row, update status, commit."""
    engine = _make_engine(db_url, use_client_cursor)
    session_factory = sessionmaker(bind=engine)

    try:
        barrier.wait(timeout=10)
        session = session_factory()
        try:
            stmt = select(ProcessTable).where(ProcessTable.process_id == process_id).with_for_update()
            result = session.execute(stmt)
            locked_process = result.scalar_one()

            # Simulate brief work
            time.sleep(0.1)

            locked_process.last_step = f"worker-{worker_id}"
            session.commit()
            results[worker_id] = "success"
        except Exception as e:
            session.rollback()
            results[worker_id] = f"error: {e}"
        finally:
            session.close()
    except Exception as e:
        results[worker_id] = f"barrier_error: {e}"
    finally:
        engine.dispose()


@pytest.mark.parametrize("use_client_cursor", [False, True], ids=["server-side", "client-side"])
def test_concurrent_for_update(use_client_cursor):
    """Test that 3 concurrent threads can sequentially acquire FOR UPDATE locks without deadlock.

    Reproduces the production scenario where multiple Celery workers try to lock the same
    ProcessTable row. Tests both server-side binding (psycopg3 default) and client-side
    binding (psycopg2 behavior via ClientCursor).
    """
    num_workers = 3
    db_url = db.engine.url.render_as_string(hide_password=False)

    # Create a workflow and process to lock
    wf = WorkflowTable(name=f"test-concurrency-{uuid4()}", target=Target.CREATE, description="Concurrency test")
    db.session.add(wf)
    db.session.flush()

    process = ProcessTable(
        workflow_id=wf.workflow_id,
        last_status=ProcessStatus.CREATED,
        last_step="initial",
        created_by="test",
        is_task=False,
    )
    db.session.add(process)
    db.session.commit()

    process_id = process.process_id

    # Run concurrent workers
    barrier = threading.Barrier(num_workers, timeout=10)
    results: dict[int, str] = {}
    threads = []

    for i in range(num_workers):
        t = threading.Thread(
            target=_worker_lock_and_update,
            args=(db_url, process_id, i, barrier, results, use_client_cursor),
        )
        threads.append(t)
        t.start()

    # Wait with timeout slightly above lock_timeout (30s) + buffer
    for t in threads:
        t.join(timeout=35)

    # Verify all threads completed
    hung_threads = [t for t in threads if t.is_alive()]
    assert not hung_threads, f"{len(hung_threads)} threads are still hanging (likely deadlocked)"

    # Verify all workers succeeded
    for i in range(num_workers):
        assert i in results, f"Worker {i} did not report a result"
        assert results[i] == "success", f"Worker {i} failed: {results[i]}"

    # Check no idle-in-transaction sessions remain
    idle_count = get_idle_in_transaction_count(db.engine)
    assert idle_count == 0, f"Found {idle_count} idle-in-transaction sessions after test"
```

- [ ] **Step 2: Run the test to see if the concurrency issue reproduces**

Run: `uv run pytest test/unit_tests/test_psycopg3_concurrency.py -v`
Expected: Observe which parameterization passes/fails. Both may pass (no deadlock in test), or server-side may fail while client-side passes.

- [ ] **Step 3: Commit**

```bash
git add test/unit_tests/test_psycopg3_concurrency.py
git commit -m "Add parameterized concurrency test for psycopg3 FOR UPDATE locking

Tests 3 concurrent threads doing SELECT ... FOR UPDATE on the same
ProcessTable row, comparing server-side vs client-side parameter binding.
Includes pg_stat_activity assertion to detect idle-in-transaction leaks."
```

---

### Task 4: Add transactional() concurrency test

**Files:**
- Modify: `test/unit_tests/test_psycopg3_concurrency.py`

- [ ] **Step 1: Write a test that uses the actual transactional() context manager**

This test is closer to the real workflow execution path. Append to the test file:

```python
from orchestrator.db import transactional
from unittest import mock


def _worker_transactional(
    db_url: str,
    process_id,
    worker_id: int,
    barrier: threading.Barrier,
    results: dict,
    use_client_cursor: bool,
):
    """Worker thread using the actual transactional() context manager."""
    engine = _make_engine(db_url, use_client_cursor)
    session_factory = sessionmaker(
        bind=engine, class_=WrappedSession, autocommit=False, autoflush=True,
    )

    try:
        barrier.wait(timeout=10)
        session = session_factory()

        # Monkey-patch db.session temporarily for this thread
        original_session = None
        try:
            mock_db = mock.MagicMock()
            mock_db.session = session
            mock_log = mock.MagicMock()

            with transactional(mock_db, mock_log):
                stmt = select(ProcessTable).where(ProcessTable.process_id == process_id).with_for_update()
                result = session.execute(stmt)
                locked_process = result.scalar_one()

                time.sleep(0.1)
                locked_process.last_step = f"transactional-worker-{worker_id}"

            results[worker_id] = "success"
        except Exception as e:
            results[worker_id] = f"error: {e}"
        finally:
            session.close()
    except Exception as e:
        results[worker_id] = f"barrier_error: {e}"
    finally:
        engine.dispose()


@pytest.mark.parametrize("use_client_cursor", [False, True], ids=["server-side", "client-side"])
def test_concurrent_transactional_for_update(use_client_cursor):
    """Test concurrent FOR UPDATE locks through the transactional() context manager.

    This is closer to the real workflow execution path where transactional()
    wraps each step with disable_commit + commit + finally:rollback.
    """
    num_workers = 3
    db_url = db.engine.url.render_as_string(hide_password=False)

    wf = WorkflowTable(name=f"test-txn-concurrency-{uuid4()}", target=Target.CREATE, description="Txn concurrency")
    db.session.add(wf)
    db.session.flush()

    process = ProcessTable(
        workflow_id=wf.workflow_id,
        last_status=ProcessStatus.CREATED,
        last_step="initial",
        created_by="test",
        is_task=False,
    )
    db.session.add(process)
    db.session.commit()

    process_id = process.process_id

    barrier = threading.Barrier(num_workers, timeout=10)
    results: dict[int, str] = {}
    threads = []

    for i in range(num_workers):
        t = threading.Thread(
            target=_worker_transactional,
            args=(db_url, process_id, i, barrier, results, use_client_cursor),
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=35)

    hung_threads = [t for t in threads if t.is_alive()]
    assert not hung_threads, f"{len(hung_threads)} threads are still hanging (likely deadlocked)"

    for i in range(num_workers):
        assert i in results, f"Worker {i} did not report a result"
        assert results[i] == "success", f"Worker {i} failed: {results[i]}"

    idle_count = get_idle_in_transaction_count(db.engine)
    assert idle_count == 0, f"Found {idle_count} idle-in-transaction sessions after test"
```

- [ ] **Step 2: Run the full test file**

Run: `uv run pytest test/unit_tests/test_psycopg3_concurrency.py -v`
Expected: 4 test results (2 parameterizations x 2 tests). Compare server-side vs client-side results.

- [ ] **Step 3: Commit**

```bash
git add test/unit_tests/test_psycopg3_concurrency.py
git commit -m "Add transactional() concurrency test for psycopg3

Tests the actual transactional() context manager with concurrent
FOR UPDATE locks, reproducing the real workflow execution path."
```

---

### Task 5: Analyze results and document findings

**Files:**
- Modify: `docs/psycopg3-migration-plan.md` (add results section)

- [ ] **Step 1: Analyze test output**

Check which tests passed/failed:
- If `server-side` fails but `client-side` passes → server-side binding is the root cause, add `ClientCursor` to `ENGINE_ARGUMENTS`
- If both pass → the lock issue is not in parameter binding, investigate `transactional()` interaction further
- If both fail → the issue is in transaction lifecycle management, not binding

- [ ] **Step 2: Document findings in the migration plan**

Append a "## Testresultaten" section to `docs/psycopg3-migration-plan.md` with the actual test output and conclusion.

- [ ] **Step 3: If ClientCursor is needed, apply the fix**

Only if server-side fails and client-side passes, modify `orchestrator/db/database.py:168-175`:

```python
from psycopg import ClientCursor

ENGINE_ARGUMENTS = {
    "connect_args": {
        "connect_timeout": 10,
        "options": "-c timezone=UTC -c lock_timeout=30000 -c idle_in_transaction_session_timeout=60000",
        "cursor_factory": ClientCursor,
    },
    "pool_pre_ping": True,
    "pool_size": 60,
    "pool_reset_on_return": "rollback",
    "json_serializer": json_dumps,
    "json_deserializer": json_loads,
}
```

- [ ] **Step 4: Run full test suite to verify no regressions**

Run: `uv run pytest test/unit_tests/ -x -q`
Expected: All existing tests PASS

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "Document psycopg3 concurrency test results and apply fix if needed"
```