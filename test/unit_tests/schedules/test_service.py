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
import warnings
from unittest import mock
from uuid import NAMESPACE_DNS, uuid5

import pytest
from structlog.testing import capture_logs

import orchestrator.core.schedules as schedules
from orchestrator.core.schedules.service import index_schedule, load_schedules
from orchestrator.core.search.core.types import EntityType

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
def mock_schedule_index():
    """Patch what index_schedule calls, yielding the mocks as (linker lookup, index, remove)."""
    service = "orchestrator.core.schedules.service"
    with (
        mock.patch(f"{service}.get_linker_entries_by_schedule_ids", return_value=[]) as mock_linker_entries,
        mock.patch(f"{service}.run_indexing_for_entity") as mock_index,
        mock.patch(f"{service}.remove_entity_from_index") as mock_remove,
    ):
        yield mock_linker_entries, mock_index, mock_remove


@pytest.mark.parametrize(
    ("schedule_id", "linker_entries", "expected_indexed", "expected_removed"),
    [
        pytest.param(SCHEDULE_ID, [object()], True, False, id="existing-schedule-is-indexed"),
        pytest.param(SCHEDULE_ID, [], False, True, id="deleted-schedule-is-removed"),
        pytest.param("decorator_job", [], False, False, id="never-indexed-job-is-ignored"),
        pytest.param("None", [], False, False, id="delete-without-schedule-id-is-ignored"),
    ],
)
def test_index_schedule_indexes_or_removes(
    mock_schedule_index, schedule_id, linker_entries, expected_indexed, expected_removed
):
    mock_linker_entries, mock_index, mock_remove = mock_schedule_index
    mock_linker_entries.return_value = linker_entries

    index_schedule(schedule_id)

    mock_linker_entries.assert_called_once_with([schedule_id])
    assert mock_index.call_args_list == [mock.call(EntityType.SCHEDULE, schedule_id)] * expected_indexed
    assert mock_remove.call_args_list == [mock.call(EntityType.SCHEDULE, schedule_id)] * expected_removed


@pytest.mark.parametrize("failing", ["linker lookup", "index", "remove"])
def test_index_schedule_logs_and_swallows_failures(mock_schedule_index, failing):
    mock_linker_entries, mock_index, mock_remove = mock_schedule_index
    mock_linker_entries.return_value = [object()] if failing == "index" else []
    failing_mock = {"linker lookup": mock_linker_entries, "index": mock_index, "remove": mock_remove}[failing]
    failing_mock.side_effect = RuntimeError("index unavailable")

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


def test_index_schedule_raises_when_indexing_is_strict(mock_schedule_index, monkeypatch):
    _, _, mock_remove = mock_schedule_index
    mock_remove.side_effect = RuntimeError("index unavailable")
    monkeypatch.setattr("orchestrator.core.schedules.service.llm_settings.SEARCH_INDEXING_STRICT", True)

    with pytest.raises(RuntimeError, match="index unavailable"):
        index_schedule(SCHEDULE_ID)
