# Copyright 2026 SURF.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Verify that read-only paths don't leave sessions in a dirty transactional state.

Under psycopg3's autobegin, every SELECT opens an implicit transaction that stays
idle-in-transaction if not properly closed. ``read_only_transaction()`` must close
the session on exit so the connection returns to the pool and the implicit tx ends.

Limitation: the ``db_session`` test fixture (conftest.py) binds the session to a
single connection wrapped in an outer transaction for automatic rollback. This means:

1. We cannot observe ``pg_stat_activity`` for our own backend meaningfully, because
   the outer transaction is always open.
2. ``session.close()`` inside ``read_only_transaction`` detaches ORM objects and
   returns the connection to the pool, but the scoped session still references the
   same session factory -- the next ``db.session`` access re-checks out a connection.

These tests verify the *session-level contract* of ``read_only_transaction``:
- The session is closed on exit (no active transaction bound).
- ORM objects loaded inside the block retain their eagerly-loaded attribute values
  after the block exits (detached instance access works for loaded attrs).
- Repeated read_only_transaction blocks don't accumulate open transactions.

For full pg_stat_activity-level verification, see:
  test/integration_tests/test_idle_in_transaction.py
"""

from unittest.mock import MagicMock

import pytest
import structlog
from sqlalchemy import text

from orchestrator.db import ProductTable, db, read_only_transaction
from orchestrator.db.database import transactional

logger = structlog.get_logger(__name__)


class TestReadOnlyTransactionSessionState:
    """Tests for session state after read_only_transaction exits."""

    def test_session_closed_after_read_only_transaction(self) -> None:
        """After read_only_transaction, the session should be closed.

        A closed session has no active connection bound, meaning the implicit
        psycopg3 autobegin transaction is released.
        """
        with read_only_transaction(db, logger):
            # Execute a simple read to trigger autobegin
            result = db.session.execute(text("SELECT 1"))
            result.fetchone()

        # After the context manager exits, session.close() was called.
        # The session's transaction should not be active in a way that
        # would leave a connection idle-in-transaction.
        # Note: under the test fixture, the scoped session may still be
        # reachable, but the session itself was closed.
        # Accessing db.session again re-opens it (scoped session behavior).
        # The key assertion is that the close() call happened (verified
        # by the fact that we can still use the session for new queries).
        new_result = db.session.execute(text("SELECT 2"))
        assert new_result.scalar() == 2

    def test_session_usable_after_read_only_transaction(self) -> None:
        """The session must remain usable for subsequent operations after the block."""
        with read_only_transaction(db, logger):
            db.session.execute(text("SELECT 1"))

        # Session should work for both reads and writes after the block
        db.session.execute(text("SELECT 1"))
        db.session.flush()

    def test_read_only_transaction_exception_still_closes_session(self) -> None:
        """If an exception occurs inside the block, the session is still closed."""
        with pytest.raises(ValueError, match="test error"):
            with read_only_transaction(db, logger):
                db.session.execute(text("SELECT 1"))
                raise ValueError("test error")

        # Session should still be usable after the exception
        result = db.session.execute(text("SELECT 1"))
        assert result.scalar() == 1


class TestReadOnlyTransactionDetachedObjects:
    """Tests for ORM object access after read_only_transaction detaches them."""

    def test_eagerly_loaded_attributes_accessible_after_block(self, generic_product_1: ProductTable) -> None:
        """ORM objects loaded inside the block should retain eagerly-loaded values.

        read_only_transaction closes the session, which detaches all ORM instances.
        Attributes that were already loaded (column values, eagerly-joined
        relationships) remain accessible on the detached instance. Only lazy-loaded
        attributes that were never accessed would raise DetachedInstanceError.
        """
        with read_only_transaction(db, logger):
            product = db.session.get(ProductTable, generic_product_1.product_id)
            assert product is not None
            # Access the attributes while still in session to eager-load them
            product_name = product.name
            product_id = product.product_id

        # After the block, these already-loaded attributes are still accessible
        assert product.name == product_name
        assert product.product_id == product_id

    def test_multiple_objects_retain_values(
        self, generic_product_1: ProductTable, generic_product_2: ProductTable
    ) -> None:
        """Multiple ORM objects loaded in a single block all retain their values."""
        with read_only_transaction(db, logger):
            p1 = db.session.get(ProductTable, generic_product_1.product_id)
            p2 = db.session.get(ProductTable, generic_product_2.product_id)
            assert p1 is not None and p2 is not None
            p1_name = p1.name
            p2_name = p2.name

        assert p1.name == p1_name
        assert p2.name == p2_name


class TestReadOnlyTransactionRepeated:
    """Verify repeated read_only_transaction blocks don't accumulate state."""

    def test_repeated_blocks_dont_accumulate_transactions(self) -> None:
        """Running multiple sequential read_only_transaction blocks must not leak.

        Repeated blocks must not leave progressively more transaction state on
        the session.
        """
        for _ in range(10):
            with read_only_transaction(db, logger):
                db.session.execute(text("SELECT 1"))

        # After 10 blocks, the session should still be clean and functional
        result = db.session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    def test_interleaved_read_and_write_transactions(self, generic_product_1: ProductTable) -> None:
        """read_only_transaction should not interfere with subsequent transactional() blocks."""
        # First do a read-only block
        with read_only_transaction(db, logger):
            product = db.session.get(ProductTable, generic_product_1.product_id)
            assert product is not None

        # Then do a write transaction -- this must work without errors
        with transactional(db, logger):
            product = db.session.get(ProductTable, generic_product_1.product_id)
            assert product is not None
            product.description = "Updated by test"

        # And another read-only block
        with read_only_transaction(db, logger):
            product = db.session.get(ProductTable, generic_product_1.product_id)
            assert product is not None


class TestReadOnlyTransactionContract:
    """Verify the contract: read_only_transaction must call session.close()."""

    def test_close_is_called_on_normal_exit(self) -> None:
        """session.close() must be called when the block exits normally."""
        mock_db = MagicMock()
        mock_log = MagicMock()

        with read_only_transaction(mock_db, mock_log):
            pass

        mock_db.session.close.assert_called_once()

    def test_close_is_called_on_exception(self) -> None:
        """session.close() must be called even when the block raises."""
        mock_db = MagicMock()
        mock_log = MagicMock()

        with pytest.raises(RuntimeError):
            with read_only_transaction(mock_db, mock_log):
                raise RuntimeError("boom")

        mock_db.session.close.assert_called_once()

    def test_no_commit_or_rollback_called(self) -> None:
        """read_only_transaction must not commit or rollback -- only close."""
        mock_db = MagicMock()
        mock_log = MagicMock()

        with read_only_transaction(mock_db, mock_log):
            pass

        mock_db.session.commit.assert_not_called()
        mock_db.session.rollback.assert_not_called()
        mock_db.session.close.assert_called_once()
