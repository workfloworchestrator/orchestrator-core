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

"""Tests for ScheduleTraverser: field extraction from a linker row combined with its APScheduler job."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

import pytest

from orchestrator.core.db import WorkflowTable
from orchestrator.core.db.models import WorkflowApschedulerJob
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.indexing.registry import ENTITY_CONFIG_REGISTRY
from orchestrator.core.targets import Target

pytestmark = pytest.mark.search

_SCHEDULE_ID = "990e8400-e29b-41d4-a716-446655440000"
_SUBSCRIPTION_ID = "880e8400-e29b-41d4-a716-446655440000"
_WORKFLOW_ID = UUID("770e8400-e29b-41d4-a716-446655440000")
_NEXT_RUN_TIME = datetime(2026, 11, 12, 1, 0, tzinfo=UTC)

_EXPECTED_FIELDS = {
    "schedule.schedule_id": (_SCHEDULE_ID, FieldType.UUID),
    "schedule.name": ("Nightly validation", FieldType.STRING),
    "schedule.trigger": ("cron[hour='1']", FieldType.STRING),
    "schedule.next_run_time": (str(_NEXT_RUN_TIME), FieldType.DATETIME),
    "schedule.workflow_id": (str(_WORKFLOW_ID), FieldType.UUID),
    "schedule.workflow_name": ("task_validate_products", FieldType.STRING),
    "schedule.workflow_description": ("Validate products", FieldType.STRING),
    "schedule.workflow_target": ("SYSTEM", FieldType.STRING),
    "schedule.is_task": ("True", FieldType.BOOLEAN),
    "schedule.subscription_id": (_SUBSCRIPTION_ID, FieldType.UUID),
    "schedule.subscription_description": ("My subscription", FieldType.STRING),
}


def _schedule() -> WorkflowApschedulerJob:
    workflow = WorkflowTable(
        workflow_id=_WORKFLOW_ID,
        name="task_validate_products",
        description="Validate products",
        target=Target.SYSTEM,
        is_task=True,
    )
    return WorkflowApschedulerJob(workflow_id=_WORKFLOW_ID, schedule_id=_SCHEDULE_ID, workflow=workflow)


def _job(**overrides):
    job = {
        "name": "Nightly validation",
        "trigger": "cron[hour='1']",
        "next_run_time": _NEXT_RUN_TIME,
        "kwargs": {"workflow_name": "task_validate_products", "user_inputs": [{"subscription_id": _SUBSCRIPTION_ID}]},
    }
    return SimpleNamespace(**(job | overrides))


def _get_subscription(subscription_id):
    """Like the real lookup: only a known subscription has a description, anything else is a ValueError."""
    if subscription_id != _SUBSCRIPTION_ID:
        raise ValueError(f"Invalid subscription id: {subscription_id}")
    return SimpleNamespace(description="My subscription")


def _get_fields(job):
    config = ENTITY_CONFIG_REGISTRY[EntityType.SCHEDULE]
    with (
        patch("orchestrator.core.schedules.scheduler.get_scheduler_task", return_value=job) as mock_get_job,
        patch("orchestrator.core.schedules.scheduler.get_subscription", side_effect=_get_subscription),
    ):
        fields = config.traverser.get_fields(entity=_schedule(), pk_name=config.pk_name, root_name=config.root_name)
    mock_get_job.assert_called_once_with(_SCHEDULE_ID)
    return {field.path: (field.value, field.value_type) for field in fields}


def test_traverse_schedule_combines_workflow_and_job():
    assert _get_fields(_job()) == _EXPECTED_FIELDS


_NO_SUBSCRIPTION_FIELDS = ("schedule.subscription_id", "schedule.subscription_description")


@pytest.mark.parametrize(
    "user_inputs",
    [
        pytest.param([], id="no-inputs"),
        pytest.param([{"note": "no subscription"}], id="no-subscription"),
        pytest.param([{"subscription_id": "not-a-uuid"}], id="malformed-subscription-id"),
    ],
)
def test_traverse_schedule_without_a_usable_subscription_indexes_no_subscription_fields(user_inputs):
    """Job inputs are free-form: a missing or malformed subscription id is not indexed, and does not fail indexing."""
    fields = _get_fields(_job(kwargs={"user_inputs": user_inputs}))

    assert fields == {path: field for path, field in _EXPECTED_FIELDS.items() if path not in _NO_SUBSCRIPTION_FIELDS}


@pytest.mark.parametrize(
    ("overrides", "missing_path"),
    [
        pytest.param({"next_run_time": None}, "schedule.next_run_time", id="paused-job-has-no-next-run-time"),
        pytest.param({"name": None}, "schedule.name", id="unnamed-job"),
    ],
)
def test_traverse_schedule_skips_unset_job_fields(overrides, missing_path):
    expected = {path: field for path, field in _EXPECTED_FIELDS.items() if path != missing_path}

    assert _get_fields(_job(**overrides)) == expected


def test_traverse_schedule_whose_job_no_longer_exists_yields_no_fields():
    assert _get_fields(None) == {}


@pytest.mark.parametrize(
    ("get_job", "expected_error"),
    [
        pytest.param({"side_effect": ConnectionError("database unavailable")}, ConnectionError, id="job-read-fails"),
        pytest.param({"return_value": SimpleNamespace(name="No trigger")}, AttributeError, id="job-cannot-be-loaded"),
    ],
)
def test_traverse_schedule_raises_when_the_job_cannot_be_read(get_job, expected_error):
    """A failed read must not look like a job that is gone: no fields would erase the schedule from the index."""
    config = ENTITY_CONFIG_REGISTRY[EntityType.SCHEDULE]

    with (
        patch("orchestrator.core.schedules.scheduler.get_scheduler_task", **get_job),
        pytest.raises(expected_error),
    ):
        config.traverser.get_fields(entity=_schedule(), pk_name=config.pk_name, root_name=config.root_name)
