# Copyright 2026 SURF.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
"""Integration test guarding against the psycopg3 idle-in-transaction read-path leak.

Background: on branch ``psycopg_v3`` we observed that read-path code (e.g.
``SubscriptionModel.from_subscription``) wrapped in ``transactional()`` would, under
psycopg3 autobegin semantics, leave the underlying PG connection ``idle in
transaction`` if the surrounding scope did not commit/rollback before
``scoped_session.remove()`` ran. The 2026-04-29 fix pre-serialised input_state to
avoid the specific deadlock; this test guards the more general invariant:

    After exercising a read-path through ``database_scope()``, no PG backend
    started during the scope is left in ``idle in transaction`` once the scope
    exits.

The test uses an independent **observer** psycopg3 connection (autocommit) to read
``pg_stat_activity`` so it never participates in the SQLAlchemy session under test.
"""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest
from sqlalchemy.engine.url import make_url

from orchestrator.db import db
from orchestrator.db.database import transactional
from orchestrator.domain.base import SubscriptionModel


def _observer_dsn(sqla_dsn: str) -> str:
    """Convert a SQLAlchemy DSN (postgresql+psycopg://...) to a pure libpq DSN."""
    url = make_url(sqla_dsn)
    return (
        f"host={url.host or 'localhost'} "
        f"port={url.port or 5432} "
        f"user={url.username} "
        f"password={url.password} "
        f"dbname={url.database}"
    )


@pytest.fixture
def observer(db_uri: str) -> Iterator[psycopg.Connection]:
    """Independent autocommit psycopg3 connection for inspecting pg_stat_activity."""
    conn = psycopg.connect(_observer_dsn(db_uri), autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


def _idle_in_tx_pids(observer: psycopg.Connection, datname: str) -> list[tuple[int, str | None, str | None]]:
    """Return (pid, application_name, query) tuples for idle-in-tx backends on ``datname``."""
    with observer.cursor() as cur:
        cur.execute(
            """
            SELECT pid, application_name, query
            FROM pg_stat_activity
            WHERE state = 'idle in transaction'
              AND datname = %s
              AND pid <> pg_backend_pid()
            """,
            (datname,),
        )
        return list(cur.fetchall())


def _backend_pid(session) -> int:  # type: ignore[no-untyped-def]
    """Get the PostgreSQL backend PID for the current SQLAlchemy session connection."""
    raw = session.connection().connection.dbapi_connection
    # psycopg3 connection exposes .info.backend_pid
    return raw.info.backend_pid  # type: ignore[no-any-return]


def test_from_subscription_does_not_leak_idle_in_transaction(
    db_uri: str,
    observer: psycopg.Connection,
    generic_subscription_1: str,
) -> None:
    """Reading a subscription must not leave the PG backend idle in transaction.

    Reproduces (in miniature) the read-path that the 4-call modify_fw scenario
    exercises through ``post_form`` -> ``from_subscription`` calls. Uses
    ``transactional()`` to mirror the production wrapping.
    """
    datname = make_url(db_uri).database
    assert datname, f"could not extract database name from {db_uri!r}"

    # NB: the autouse ``db_session`` fixture wraps this test in an outer
    # connection-level transaction, so the test's own backend PID will appear
    # idle-in-tx during the test. We compare counts before/after to guard
    # against *additional* leaks. The expected count after equals the count
    # before: zero new idle-in-tx backends.
    leaks_before = {pid for pid, _app, _q in _idle_in_tx_pids(observer, datname)}

    # Drive the read path that historically leaked
    with transactional(db, __import__("structlog").get_logger(__name__)):
        sub = SubscriptionModel.from_subscription(generic_subscription_1)
        assert sub.subscription_id is not None

    # Force expiration of any lingering SQL state on the session
    db.session.expire_all()

    leaks_after = {pid for pid, _app, _q in _idle_in_tx_pids(observer, datname)}

    new_leaks = leaks_after - leaks_before
    assert not new_leaks, (
        f"Read path left {len(new_leaks)} new backend(s) idle in transaction: "
        f"PIDs={sorted(new_leaks)}; details={[(p, a, q) for p, a, q in _idle_in_tx_pids(observer, datname) if p in new_leaks]}"
    )


def test_repeat_from_subscription_no_growing_leak(
    db_uri: str,
    observer: psycopg.Connection,
    generic_subscription_1: str,
) -> None:
    """Looping the read path mirrors the 4-call sequence — leak count must stay stable."""
    datname = make_url(db_uri).database
    assert datname

    baseline = len(_idle_in_tx_pids(observer, datname))

    log = __import__("structlog").get_logger(__name__)
    for _ in range(4):
        with transactional(db, log):
            SubscriptionModel.from_subscription(generic_subscription_1)
        db.session.expire_all()

    after = len(_idle_in_tx_pids(observer, datname))
    assert after <= baseline, (
        f"idle-in-tx connection count grew from {baseline} to {after} after 4 reads; "
        "indicates a per-call leak"
    )
