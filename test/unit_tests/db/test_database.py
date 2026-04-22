# Copyright 2019-2026 SURF.
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

"""Tests for database session management: WrappedSession commit gating, disable_commit nesting, and transactional."""

from unittest.mock import MagicMock, patch

import pytest

from orchestrator.core.db.database import (
    WrappedSession,
    disable_commit,
    transactional,
)


def _make_db(disabled: bool = False) -> MagicMock:
    db = MagicMock()
    db.session.info = {"disabled": disabled}
    return db


def _make_session(disabled: bool = False, custom_logger: MagicMock | None = None) -> MagicMock:
    session = MagicMock(spec=WrappedSession)
    session.info = {"disabled": disabled}
    if custom_logger is not None:
        session.info["logger"] = custom_logger
    session.commit = WrappedSession.commit.__get__(session, WrappedSession)
    return session


# --- WrappedSession.commit ---


@pytest.mark.parametrize(
    "disabled,expect_super_called",
    [
        pytest.param(False, True, id="enabled-calls-super"),
        pytest.param(True, False, id="disabled-skips-super"),
    ],
)
def test_wrapped_session_commit_respects_disabled_flag(disabled: bool, expect_super_called: bool) -> None:
    session = _make_session(disabled=disabled)
    with patch("orchestrator.core.db.database.Session.commit") as mock_super:
        session.commit()
    assert mock_super.called == expect_super_called


def test_wrapped_session_commit_disabled_logs_warning() -> None:
    mock_log = MagicMock()
    session = _make_session(disabled=True, custom_logger=mock_log)
    with patch("orchestrator.core.db.database.Session.commit"):
        session.commit()
    mock_log.warning.assert_called_once()


# --- disable_commit ---


def test_disable_commit_sets_and_restores_state() -> None:
    db = _make_db(disabled=False)
    log = MagicMock()
    with disable_commit(db, log):
        assert db.session.info["disabled"] is True
        assert db.session.info["logger"] is log
    _assert_state(db, disabled=False, logger=None)


def _assert_state(db: MagicMock, *, disabled: bool, logger: object) -> None:
    assert db.session.info["disabled"] is disabled
    assert db.session.info["logger"] is logger


def test_disable_commit_nested_does_not_reenable() -> None:
    db = _make_db(disabled=True)
    log = MagicMock()
    with disable_commit(db, log):
        assert db.session.info["disabled"] is True
    assert db.session.info["disabled"] is True
    log.debug.assert_not_called()


@pytest.mark.parametrize(
    "exc_type",
    [pytest.param(ValueError, id="value-error"), pytest.param(RuntimeError, id="runtime-error")],
)
def test_disable_commit_restores_on_exception(exc_type: type[Exception]) -> None:
    db = _make_db(disabled=False)
    log = MagicMock()
    with pytest.raises(exc_type):
        with disable_commit(db, log):
            raise exc_type("boom")
    assert db.session.info["disabled"] is False
    assert db.session.info["logger"] is None


# --- transactional ---


def test_transactional_commits_on_success() -> None:
    db = _make_db()
    log = MagicMock()
    with transactional(db, log):
        pass
    db.session.commit.assert_called_once()
    db.session.rollback.assert_called_once()


def test_transactional_does_not_commit_on_exception() -> None:
    db = _make_db()
    log = MagicMock()
    with pytest.raises(RuntimeError):
        with transactional(db, log):
            raise RuntimeError("step failed")
    db.session.commit.assert_not_called()
    db.session.rollback.assert_called_once()
    log.warning.assert_called_once()


def test_transactional_disables_commit_inside_block() -> None:
    db = _make_db()
    log = MagicMock()
    captured: dict = {}
    with transactional(db, log):
        captured["disabled"] = db.session.info.get("disabled")
    assert captured["disabled"] is True
    assert db.session.info.get("disabled") is False


def test_transactional_nested_does_not_commit_or_rollback() -> None:
    """Nested transactional() must not commit or rollback even after a real session operation."""
    db = _make_db(disabled=True)  # simulate already inside an outer transactional()
    log = MagicMock()

    with transactional(db, log):
        db.session.add(MagicMock())  # simulate a real write

    db.session.commit.assert_not_called()
    db.session.rollback.assert_not_called()


def test_transactional_nested_propagates_exception_without_rollback() -> None:
    """Nested transactional() must propagate exceptions without rollback after a real session operation."""
    db = _make_db(disabled=True)
    log = MagicMock()

    with pytest.raises(RuntimeError, match="inner failed"):
        with transactional(db, log):
            db.session.add(MagicMock())  # simulate a real write
            raise RuntimeError("inner failed")

    db.session.commit.assert_not_called()
    db.session.rollback.assert_not_called()
