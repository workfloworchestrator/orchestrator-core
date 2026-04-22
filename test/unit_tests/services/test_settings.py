# Copyright 2019-2026 SURF, GÉANT.
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

"""Tests for engine settings: global status computation, Slack notification, search index refresh, and schema generation."""

from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import RequestException
from sqlalchemy.exc import SQLAlchemyError

from orchestrator.core.schemas.engine_settings import EngineSettingsSchema, GlobalStatusEnum
from orchestrator.core.services.settings import (
    generate_engine_global_status,
    generate_engine_settings_schema,
    post_update_to_slack,
    reset_search_index,
)


def _make_engine_settings(*, global_lock: bool) -> MagicMock:
    settings = MagicMock()
    settings.global_lock = global_lock
    return settings


@pytest.mark.parametrize(
    "global_lock, running_count, expected_status",
    [
        (True, 5, GlobalStatusEnum.PAUSING),
        (True, 1, GlobalStatusEnum.PAUSING),
        (True, 0, GlobalStatusEnum.PAUSED),
        (False, 0, GlobalStatusEnum.RUNNING),
        (False, 5, GlobalStatusEnum.RUNNING),
        (False, 100, GlobalStatusEnum.RUNNING),
    ],
    ids=[
        "locked_and_running_returns_pausing",
        "locked_and_one_running_returns_pausing",
        "locked_and_no_running_returns_paused",
        "unlocked_and_no_running_returns_running",
        "unlocked_and_running_returns_running",
        "unlocked_and_many_running_returns_running",
    ],
)
def test_generate_engine_global_status(global_lock: bool, running_count: int, expected_status: GlobalStatusEnum):
    engine_settings = _make_engine_settings(global_lock=global_lock)
    result = generate_engine_global_status(engine_settings, running_count)
    assert result == expected_status


@pytest.mark.parametrize(
    "global_lock, expected_action_fragment",
    [
        (True, "pause all running processes"),
        (False, "pick up all pending processes"),
    ],
    ids=["lock_true_posts_stop_message", "lock_false_posts_start_message"],
)
def test_post_update_to_slack_sends_correct_message(global_lock: bool, expected_action_fragment: str):
    engine_status = MagicMock(spec=EngineSettingsSchema)
    engine_status.global_lock = global_lock

    with patch("orchestrator.core.services.settings.requests.post") as mock_post:
        with patch("orchestrator.core.services.settings.app_settings") as mock_app_settings:
            mock_app_settings.ENVIRONMENT = "test-env"
            mock_app_settings.SLACK_ENGINE_SETTINGS_HOOK_URL = "https://hooks.slack.example/test"

            post_update_to_slack(engine_status, "testuser")

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    message_text = call_kwargs.kwargs["json"]["text"]
    assert "testuser" in message_text
    assert expected_action_fragment in message_text


def test_post_update_to_slack_handles_request_exception_silently():
    engine_status = MagicMock(spec=EngineSettingsSchema)
    engine_status.global_lock = False

    with patch("orchestrator.core.services.settings.requests.post", side_effect=RequestException("network error")):
        with patch("orchestrator.core.services.settings.app_settings") as mock_app_settings:
            mock_app_settings.ENVIRONMENT = "test-env"
            mock_app_settings.SLACK_ENGINE_SETTINGS_HOOK_URL = "https://hooks.slack.example/test"
            # Must not raise
            post_update_to_slack(engine_status, "testuser")


def test_reset_search_index_executes_refresh():
    mock_session = MagicMock()

    with patch("orchestrator.core.services.settings.db") as mock_db:
        mock_db.session = mock_session
        reset_search_index()

    mock_session.execute.assert_called_once()
    executed_sql = str(mock_session.execute.call_args[0][0])
    assert "REFRESH MATERIALIZED VIEW" in executed_sql
    mock_session.commit.assert_not_called()


def test_reset_search_index_commits_when_tx_commit_true():
    mock_session = MagicMock()

    with patch("orchestrator.core.services.settings.db") as mock_db:
        mock_db.session = mock_session
        reset_search_index(tx_commit=True)

    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


def test_reset_search_index_raises_and_commits_when_tx_commit_true_on_error():
    mock_session = MagicMock()
    mock_session.execute.side_effect = SQLAlchemyError("DB error")

    with patch("orchestrator.core.services.settings.db") as mock_db:
        mock_db.session = mock_session
        with pytest.raises(SQLAlchemyError):
            reset_search_index(tx_commit=True)

    mock_session.commit.assert_called_once()


def test_reset_search_index_raises_without_commit_when_tx_commit_false_on_error():
    mock_session = MagicMock()
    mock_session.execute.side_effect = SQLAlchemyError("DB error")

    with patch("orchestrator.core.services.settings.db") as mock_db:
        mock_db.session = mock_session
        with pytest.raises(SQLAlchemyError):
            reset_search_index(tx_commit=False)

    mock_session.commit.assert_not_called()


def test_generate_engine_settings_schema_returns_correct_schema():
    engine_settings = _make_engine_settings(global_lock=False)
    mock_monitor = MagicMock()
    mock_monitor.get_running_jobs_count.return_value = 3

    with patch("orchestrator.core.services.settings.get_worker_status_monitor", return_value=mock_monitor):
        result = generate_engine_settings_schema(engine_settings)

    assert isinstance(result, EngineSettingsSchema)
    assert result.global_lock is False
    assert result.running_processes == 3
    assert result.global_status == GlobalStatusEnum.RUNNING


def test_generate_engine_settings_schema_pausing_when_locked_and_running():
    engine_settings = _make_engine_settings(global_lock=True)
    mock_monitor = MagicMock()
    mock_monitor.get_running_jobs_count.return_value = 2

    with patch("orchestrator.core.services.settings.get_worker_status_monitor", return_value=mock_monitor):
        result = generate_engine_settings_schema(engine_settings)

    assert result.global_lock is True
    assert result.running_processes == 2
    assert result.global_status == GlobalStatusEnum.PAUSING


def test_generate_engine_settings_schema_paused_when_locked_and_idle():
    engine_settings = _make_engine_settings(global_lock=True)
    mock_monitor = MagicMock()
    mock_monitor.get_running_jobs_count.return_value = 0

    with patch("orchestrator.core.services.settings.get_worker_status_monitor", return_value=mock_monitor):
        result = generate_engine_settings_schema(engine_settings)

    assert result.global_lock is True
    assert result.running_processes == 0
    assert result.global_status == GlobalStatusEnum.PAUSED
