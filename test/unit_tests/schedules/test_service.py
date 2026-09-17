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

"""Tests for load_schedules, the entry point for registering schedules from code."""

from unittest.mock import Mock
from uuid import NAMESPACE_DNS, uuid5

import pytest

from orchestrator.core.schedules.service import load_schedules


@pytest.mark.parametrize("mock_add_schedule", [["my_task"]], indirect=True)
def test_load_schedules_enriches_workflow_id_and_passes_recreate(mock_add_schedule: Mock) -> None:
    schedule = {"name": "My Task", "workflow_name": "my_task", "trigger": "interval", "trigger_kwargs": {"hours": 2}}

    assert load_schedules([schedule], recreate=True) == []

    payload = mock_add_schedule.call_args.args[0]
    assert payload.workflow_id == uuid5(NAMESPACE_DNS, "my_task")
    assert (payload.name, payload.trigger, payload.trigger_kwargs) == ("My Task", "interval", {"hours": 2})
    assert mock_add_schedule.call_args.kwargs == {"recreate": True}


@pytest.mark.parametrize("mock_add_schedule", [["known_task"]], indirect=True)
def test_load_schedules_returns_unknown_workflow_names(mock_add_schedule: Mock) -> None:
    schedules = [
        {"name": "Known", "workflow_name": "known_task", "trigger": "interval", "trigger_kwargs": {"hours": 1}},
        {"name": "Unknown", "workflow_name": "missing_task", "trigger": "interval", "trigger_kwargs": {"hours": 1}},
    ]

    assert load_schedules(schedules) == ["missing_task"]
    assert mock_add_schedule.call_count == 1


@pytest.mark.parametrize("mock_add_schedule", [[]], indirect=True)
@pytest.mark.parametrize("workflow_name", [pytest.param("", id="empty"), pytest.param(None, id="none")])
def test_load_schedules_reports_falsy_workflow_names(mock_add_schedule: Mock, workflow_name: str | None) -> None:
    """A name that is empty or None registers nothing, so it must still be reported as skipped."""
    schedule = {"name": "Bad", "workflow_name": workflow_name, "trigger": "interval", "trigger_kwargs": {"hours": 1}}

    assert load_schedules([schedule]) == [str(workflow_name)]
    assert mock_add_schedule.call_count == 0
