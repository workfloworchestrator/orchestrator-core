"""Tests for database_scope() cleanup semantics and session-factory config."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from orchestrator.db import db


def _real_db() -> object:
    """Return the underlying Database instance behind the WrappedDatabase proxy."""
    # ``db`` is a WrappedDatabase that proxies attribute access via __getattr__.
    # For monkeypatching we need to reach the real Database object.
    from orchestrator.db import wrapped_db

    assert wrapped_db.wrapped_database is not None
    return wrapped_db.wrapped_database


def test_database_scope_cleans_up_on_setup_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """If session-factory raises during scope entry, ContextVar must still reset."""
    real_db = _real_db()
    before_token = real_db.request_context.get()  # type: ignore[attr-defined]

    class BoomError(RuntimeError):
        pass

    monkeypatch.setattr(real_db, "scoped_session", MagicMock(side_effect=BoomError("boom")))

    with pytest.raises(BoomError):
        with db.database_scope():
            pass  # pragma: no cover - never reached

    assert real_db.request_context.get() == before_token  # type: ignore[attr-defined]
