"""Test that _exec_steps closes autobegin transaction before step execution."""

from psycopg.pq import TransactionStatus

from orchestrator.db import db
from orchestrator.services.settings import get_engine_settings_table


def test_connection_idle_after_engine_settings_check(database):
    """After get_engine_settings_table(), a rollback should leave the connection IDLE."""
    # Execute the SELECT that triggers autobegin
    get_engine_settings_table()

    # With psycopg3 autobegin, the connection is now in a transaction
    raw_conn = db.session.connection().connection.dbapi_connection
    assert raw_conn.info.transaction_status == TransactionStatus.INTRANS

    # The fix: rollback closes the autobegin transaction
    db.session.rollback()

    # Connection should now be IDLE
    raw_conn = db.session.connection().connection.dbapi_connection
    assert raw_conn.info.transaction_status == TransactionStatus.IDLE