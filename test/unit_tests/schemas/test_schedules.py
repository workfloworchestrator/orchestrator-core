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

"""Tests for APScheduler job schemas — focuses on discriminated union dispatch via APSJobAdapter."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from orchestrator.core.schemas.schedules import (
    APSchedulerJobCreate,
    APSchedulerJobDelete,
    APSchedulerJobUpdate,
    APSJobAdapter,
)

WORKFLOW_ID = uuid4()
SCHEDULE_ID = uuid4()


@pytest.mark.parametrize(
    "data,expected_type",
    [
        pytest.param(
            {"scheduled_type": "create", "workflow_name": "wf", "workflow_id": str(WORKFLOW_ID), "trigger": "interval"},
            APSchedulerJobCreate,
            id="create",
        ),
        pytest.param(
            {"scheduled_type": "update", "schedule_id": str(SCHEDULE_ID)},
            APSchedulerJobUpdate,
            id="update",
        ),
        pytest.param(
            {"scheduled_type": "delete", "workflow_id": str(WORKFLOW_ID)},
            APSchedulerJobDelete,
            id="delete",
        ),
    ],
)
def test_adapter_dispatches_to_correct_type(data: dict, expected_type: type) -> None:
    job = APSJobAdapter.validate_python(data)
    assert isinstance(job, expected_type)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"scheduled_type": "unknown"}, id="invalid-discriminator"),
        pytest.param({"workflow_name": "wf"}, id="missing-discriminator"),
    ],
)
def test_adapter_rejects_invalid_input(data: dict) -> None:
    with pytest.raises(ValidationError):
        APSJobAdapter.validate_python(data)


CREATE_BASE = {"scheduled_type": "create", "workflow_name": "wf", "workflow_id": str(WORKFLOW_ID)}


@pytest.mark.parametrize(
    "trigger,trigger_kwargs",
    [
        pytest.param("cron", {"minute": "*/15"}, id="cron-valid"),
        pytest.param("cron", {"second": "*/15", "minute": "*"}, id="cron-6-field"),
        pytest.param("interval", {"hours": 12}, id="interval-valid"),
        pytest.param("cron", {}, id="empty-kwargs-ok"),
    ],
)
def test_create_accepts_valid_trigger_kwargs(trigger: str, trigger_kwargs: dict) -> None:
    job = APSchedulerJobCreate.model_validate({**CREATE_BASE, "trigger": trigger, "trigger_kwargs": trigger_kwargs})
    assert job.trigger_kwargs == trigger_kwargs


@pytest.mark.parametrize(
    "trigger,trigger_kwargs",
    [
        pytest.param("cron", {"minute": "61"}, id="cron-minute-oob"),
        pytest.param("cron", {"day_of_week": "8"}, id="cron-dow-oob"),
        pytest.param("interval", {"hours": "not-a-number"}, id="interval-bad-type"),
    ],
)
def test_create_rejects_invalid_trigger_kwargs(trigger: str, trigger_kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        APSchedulerJobCreate.model_validate({**CREATE_BASE, "trigger": trigger, "trigger_kwargs": trigger_kwargs})


def test_update_rejects_invalid_trigger_kwargs() -> None:
    with pytest.raises(ValidationError):
        APSchedulerJobUpdate.model_validate(
            {
                "scheduled_type": "update",
                "schedule_id": str(SCHEDULE_ID),
                "trigger": "cron",
                "trigger_kwargs": {"minute": "61"},
            }
        )


def test_update_without_trigger_skips_validation() -> None:
    # trigger/trigger_kwargs are optional on update; nothing to validate when trigger is absent
    job = APSchedulerJobUpdate.model_validate(
        {"scheduled_type": "update", "schedule_id": str(SCHEDULE_ID), "name": "renamed"}
    )
    assert job.trigger is None
