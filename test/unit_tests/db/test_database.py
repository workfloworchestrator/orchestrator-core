# Copyright 2019-2020 SURF.
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

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Query

from orchestrator.db.database import (
    ENGINE_ARGUMENTS,
    SESSION_ARGUMENTS,
    NoSessionError,
    SearchQuery,
    WrappedSession,
    disable_commit,
    transactional,
)
from orchestrator.utils.json import json_dumps, json_loads


def _make_db(disabled: bool = False) -> MagicMock:
    db = MagicMock()
    db.session.info = {"disabled": disabled}
    return db


class TestSearchQuery:
    def test_search_query_is_subclass_of_query(self):
        assert issubclass(SearchQuery, Query)


class TestNoSessionError:
    def test_no_session_error_is_subclass_of_runtime_error(self):
        assert issubclass(NoSessionError, RuntimeError)

    def test_no_session_error_can_be_raised(self):
        with pytest.raises(NoSessionError, match="test message"):
            raise NoSessionError("test message")

    def test_no_session_error_can_be_caught_as_runtime_error(self):
        with pytest.raises(RuntimeError):
            raise NoSessionError("caught as RuntimeError")


class TestEngineArguments:
    def test_engine_arguments_connect_timeout(self):
        assert ENGINE_ARGUMENTS["connect_args"]["connect_timeout"] == 10

    def test_engine_arguments_timezone_utc(self):
        assert ENGINE_ARGUMENTS["connect_args"]["options"] == "-c timezone=UTC"

    def test_engine_arguments_pool_pre_ping(self):
        assert ENGINE_ARGUMENTS["pool_pre_ping"] is True

    def test_engine_arguments_pool_size(self):
        assert ENGINE_ARGUMENTS["pool_size"] == 60

    def test_engine_arguments_json_serializer(self):
        assert ENGINE_ARGUMENTS["json_serializer"] is json_dumps

    def test_engine_arguments_json_deserializer(self):
        assert ENGINE_ARGUMENTS["json_deserializer"] is json_loads


class TestSessionArguments:
    def test_session_arguments_class(self):
        assert SESSION_ARGUMENTS["class_"] is WrappedSession

    def test_session_arguments_autocommit_false(self):
        assert SESSION_ARGUMENTS["autocommit"] is False

    def test_session_arguments_autoflush_true(self):
        assert SESSION_ARGUMENTS["autoflush"] is True

    def test_session_arguments_query_cls(self):
        assert SESSION_ARGUMENTS["query_cls"] is SearchQuery


class TestWrappedSession:
    def _make_session(self, disabled: bool = False, custom_logger=None) -> WrappedSession:
        """Build a WrappedSession with info pre-populated, without a real DB."""
        session = MagicMock(spec=WrappedSession)
        session.info = {"disabled": disabled}
        if custom_logger is not None:
            session.info["logger"] = custom_logger
        # Bind the real commit method to our mock session so we can inspect calls
        session.commit = WrappedSession.commit.__get__(session, WrappedSession)
        return session

    def test_commit_when_not_disabled_calls_super(self):
        session = self._make_session(disabled=False)
        with patch("orchestrator.db.database.Session.commit") as mock_super_commit:
            session.commit()
            mock_super_commit.assert_called_once()

    def test_commit_when_disabled_does_not_call_super(self):
        session = self._make_session(disabled=True)
        with patch("orchestrator.db.database.Session.commit") as mock_super_commit:
            session.commit()
            mock_super_commit.assert_not_called()

    def test_commit_when_disabled_logs_warning(self):
        mock_log = MagicMock()
        session = self._make_session(disabled=True, custom_logger=mock_log)
        with patch("orchestrator.db.database.Session.commit"):
            session.commit()
        mock_log.warning.assert_called_once()

    def test_commit_when_disabled_uses_fallback_logger_when_no_logger_in_info(self):
        session = self._make_session(disabled=True)
        # No custom logger in info — falls back to module-level logger
        with patch("orchestrator.db.database.Session.commit"):
            with patch("orchestrator.db.database.logger") as mock_module_logger:
                session.commit()
        mock_module_logger.warning.assert_called_once()


class TestDisableCommit:
    def test_disable_commit_sets_disabled_true(self):
        db = _make_db(disabled=False)
        log = MagicMock()
        with disable_commit(db, log):
            assert db.session.info["disabled"] is True

    def test_disable_commit_restores_disabled_false_after_exit(self):
        db = _make_db(disabled=False)
        log = MagicMock()
        with disable_commit(db, log):
            pass
        assert db.session.info["disabled"] is False

    def test_disable_commit_sets_logger_in_session_info(self):
        db = _make_db(disabled=False)
        log = MagicMock()
        with disable_commit(db, log):
            assert db.session.info["logger"] is log

    def test_disable_commit_clears_logger_after_exit(self):
        db = _make_db(disabled=False)
        log = MagicMock()
        with disable_commit(db, log):
            pass
        assert db.session.info["logger"] is None

    def test_disable_commit_logs_debug_on_entry_and_exit(self):
        db = _make_db(disabled=False)
        log = MagicMock()
        with disable_commit(db, log):
            pass
        assert log.debug.call_count == 2

    def test_disable_commit_nested_already_disabled_does_not_restore(self):
        """When commit is already disabled (nested), we must not re-enable it on exit."""
        db = _make_db(disabled=True)
        log = MagicMock()
        with disable_commit(db, log):
            assert db.session.info["disabled"] is True
        # Should still be disabled after inner context exits
        assert db.session.info["disabled"] is True

    def test_disable_commit_nested_does_not_log(self):
        db = _make_db(disabled=True)
        log = MagicMock()
        with disable_commit(db, log):
            pass
        log.debug.assert_not_called()

    def test_disable_commit_restores_on_exception(self):
        db = _make_db(disabled=False)
        log = MagicMock()
        with pytest.raises(ValueError):
            with disable_commit(db, log):
                raise ValueError("boom")
        assert db.session.info["disabled"] is False

    def test_disable_commit_clears_logger_on_exception(self):
        db = _make_db(disabled=False)
        log = MagicMock()
        with pytest.raises(RuntimeError):
            with disable_commit(db, log):
                raise RuntimeError("error")
        assert db.session.info["logger"] is None


class TestTransactional:
    def test_transactional_commits_on_success(self):
        db = _make_db()
        log = MagicMock()
        with transactional(db, log):
            pass
        db.session.commit.assert_called_once()

    def test_transactional_always_calls_rollback_in_finally(self):
        db = _make_db()
        log = MagicMock()
        with transactional(db, log):
            pass
        db.session.rollback.assert_called_once()

    def test_transactional_rollback_called_on_exception(self):
        db = _make_db()
        log = MagicMock()
        with pytest.raises(RuntimeError):
            with transactional(db, log):
                raise RuntimeError("step failed")
        db.session.rollback.assert_called_once()

    def test_transactional_does_not_commit_on_exception(self):
        db = _make_db()
        log = MagicMock()
        with pytest.raises(RuntimeError):
            with transactional(db, log):
                raise RuntimeError("step failed")
        db.session.commit.assert_not_called()

    def test_transactional_reraises_exception(self):
        db = _make_db()
        log = MagicMock()
        with pytest.raises(ValueError, match="original error"):
            with transactional(db, log):
                raise ValueError("original error")

    def test_transactional_logs_warning_on_exception(self):
        db = _make_db()
        log = MagicMock()
        with pytest.raises(RuntimeError):
            with transactional(db, log):
                raise RuntimeError("oops")
        log.warning.assert_called_once()

    def test_transactional_logs_debug_commit_on_success(self):
        db = _make_db()
        log = MagicMock()
        with transactional(db, log):
            pass
        # disable_commit logs 2 debug calls; transactional adds 1 more for commit
        assert log.debug.call_count >= 1
        debug_messages = [str(c) for c in log.debug.call_args_list]
        assert any("ommit" in msg for msg in debug_messages)

    def test_transactional_disables_commit_inside_block(self):
        db = _make_db()
        log = MagicMock()
        captured = {}
        with transactional(db, log):
            captured["disabled"] = db.session.info.get("disabled")
        assert captured["disabled"] is True

    def test_transactional_reenables_commit_after_block(self):
        db = _make_db()
        log = MagicMock()
        with transactional(db, log):
            pass
        assert db.session.info.get("disabled") is False
