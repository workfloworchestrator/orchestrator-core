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

from uuid import NAMESPACE_DNS, uuid5

import pytest

from orchestrator.core.schedules.service import load_schedules


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
