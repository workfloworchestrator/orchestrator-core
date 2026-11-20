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

"""Tests for load_schedules, the entry point for registering schedules from code, and for schedule indexing."""

import importlib
import threading
import warnings
from unittest import mock
from uuid import NAMESPACE_DNS, uuid5

import pytest
from structlog.testing import capture_logs

import orchestrator.core.schedules as schedules
from orchestrator.core.schedules.service import index_schedule, load_schedules, submit_schedule_index

SCHEDULE_ID = "990e8400-e29b-41d4-a716-446655440000"


def test_importing_schedules_does_not_warn():
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        importlib.reload(schedules)
        with pytest.raises(AttributeError):
            _ = schedules.UNKNOWN_ATTRIBUTE

    assert not caught_warnings


def test_accessing_all_schedulers_warns():
    namespace = {}
    with pytest.warns(DeprecationWarning, match=r"removed in 6\.0\.0"):
        exec("from orchestrator.core.schedules import *", namespace)  # noqa: S102
    assert namespace["ALL_SCHEDULERS"] == []


def test_load_schedules_enriches_workflow_id_and_passes_recreate(mock_schedule_queue):
    mock_add = mock_schedule_queue("my_task")
    schedule = {"name": "My Task", "workflow_name": "my_task", "trigger": "interval", "trigger_kwargs": {"hours": 2}}

    assert load_schedules([schedule], recreate=True) == []

    payload = mock_add.call_args.args[0]
    assert payload.workflow_id == uuid5(NAMESPACE_DNS, "my_task")
    assert (payload.name, payload.trigger, payload.trigger_kwargs) == ("My Task", "interval", {"hours": 2})
    assert mock_add.call_args.kwargs == {"recreate": True}


def test_load_schedules_returns_unknown_workflow_names(mock_schedule_queue):
    mock_add = mock_schedule_queue("known_task")
    schedules = [
        {"name": "Known", "workflow_name": "known_task", "trigger": "interval", "trigger_kwargs": {"hours": 1}},
        {"name": "Unknown", "workflow_name": "missing_task", "trigger": "interval", "trigger_kwargs": {"hours": 1}},
    ]

    assert load_schedules(schedules) == ["missing_task"]
    assert mock_add.call_count == 1


def test_load_schedules_rejects_duplicate_workflows(mock_schedule_queue):
    """add_unique_scheduled_task_to_queue keeps one schedule per workflow, so two is a config error."""
    mock_add = mock_schedule_queue("known_task")
    schedules = [
        {"name": "Weekdays", "workflow_name": "known_task", "trigger": "cron", "trigger_kwargs": {"hour": 1}},
        {"name": "Weekends", "workflow_name": "known_task", "trigger": "cron", "trigger_kwargs": {"hour": 23}},
    ]

    with pytest.raises(ValueError, match="Multiple schedules declared for workflow"):
        load_schedules(schedules)
    assert mock_add.call_count == 0


def test_load_schedules_queues_nothing_when_a_later_schedule_is_malformed(mock_schedule_queue):
    """Validation runs over the whole list first, so a bad entry cannot partially apply."""
    mock_add = mock_schedule_queue("known_task")
    schedules = [
        {"name": "Good", "workflow_name": "known_task", "trigger": "interval", "trigger_kwargs": {"hours": 1}},
        {"name": "Bad", "workflow_name": None, "trigger": "interval", "trigger_kwargs": {"hours": 1}},
    ]

    with pytest.raises(ValueError, match="has no valid workflow_name"):
        load_schedules(schedules)
    assert mock_add.call_count == 0


@pytest.mark.parametrize(
    "workflow_name",
    [
        pytest.param("", id="empty"),
        pytest.param(None, id="none"),
        pytest.param(123, id="int"),
        pytest.param(["task_a"], id="list"),
    ],
)
def test_load_schedules_rejects_invalid_workflow_name(mock_schedule_queue, workflow_name):
    """A name that is missing or not a string is a malformed schedule, so it fails loudly.

    Reporting it as skipped would both hide the error and break the `list[str]` return type.
    """
    mock_add = mock_schedule_queue()
    schedule = {"name": "Bad", "workflow_name": workflow_name, "trigger": "interval", "trigger_kwargs": {"hours": 1}}

    with pytest.raises(ValueError, match="has no valid workflow_name"):
        load_schedules([schedule])
    assert mock_add.call_count == 0


@pytest.fixture
def mock_run_indexing():
    with mock.patch("orchestrator.core.schedules.service.run_indexing_for_entity") as mock_index:
        yield mock_index


def test_index_schedule_logs_and_swallows_failures(mock_run_indexing):
    mock_run_indexing.side_effect = RuntimeError("index unavailable")

    with capture_logs() as logs:
        index_schedule(SCHEDULE_ID)

    assert logs == [
        {
            "event": "Failed to index schedule",
            "log_level": "warning",
            "schedule_id": SCHEDULE_ID,
            "error": "index unavailable",
        }
    ]


def test_index_schedule_raises_when_indexing_is_strict(mock_run_indexing, monkeypatch):
    mock_run_indexing.side_effect = RuntimeError("index unavailable")
    monkeypatch.setattr("orchestrator.core.schedules.service.llm_settings.SEARCH_INDEXING_STRICT", True)

    with pytest.raises(RuntimeError, match="index unavailable"):
        index_schedule(SCHEDULE_ID)


WAIT = 10


@pytest.fixture
def mock_database_scope():
    with mock.patch("orchestrator.core.schedules.service.db") as mock_db:
        yield mock_db.database_scope


def test_submit_schedule_index_indexes_on_the_index_thread_in_a_database_scope(mock_database_scope):
    index_threads: list[str] = []

    def record_thread(schedule_id: str) -> None:
        mock_database_scope.return_value.__enter__.assert_called_once_with()
        index_threads.append(threading.current_thread().name)

    with mock.patch("orchestrator.core.schedules.service.index_schedule", side_effect=record_thread) as mock_index:
        submit_schedule_index(SCHEDULE_ID).result(timeout=WAIT)

    mock_index.assert_called_once_with(SCHEDULE_ID)
    (index_thread,) = index_threads
    assert index_thread.startswith("schedule-index")
    assert index_thread != threading.current_thread().name


def test_submit_schedule_index_does_not_wait_and_keeps_the_submission_order(mock_database_scope):
    """A slow update blocks neither the caller nor the order: the next update only starts after it finished."""
    release_first = threading.Event()
    events: list[str] = []

    def slow_first_index(schedule_id: str) -> None:
        events.append(f"start {schedule_id}")
        assert schedule_id != "first" or release_first.wait(timeout=WAIT)
        events.append(f"end {schedule_id}")

    with mock.patch("orchestrator.core.schedules.service.index_schedule", side_effect=slow_first_index):
        first = submit_schedule_index("first")
        second = submit_schedule_index("second")
        returned_before_indexing_finished = not first.done() and not second.done()
        release_first.set()
        second.result(timeout=WAIT)

    assert returned_before_indexing_finished
    assert events == ["start first", "end first", "start second", "end second"]


def test_submit_schedule_index_logs_a_failure_and_keeps_indexing(mock_database_scope):
    with (
        mock.patch(
            "orchestrator.core.schedules.service.index_schedule", side_effect=[RuntimeError("index unavailable"), None]
        ) as mock_index,
        capture_logs() as logs,
    ):
        failed = submit_schedule_index("failing")
        submit_schedule_index("next").result(timeout=WAIT)

    assert isinstance(failed.exception(timeout=WAIT), RuntimeError)
    assert [(log["event"], log["log_level"], log["schedule_id"]) for log in logs] == [
        ("Failed to index schedule in the background", "error", "failing")
    ]
    assert mock_index.call_args_list == [mock.call("failing"), mock.call("next")]
