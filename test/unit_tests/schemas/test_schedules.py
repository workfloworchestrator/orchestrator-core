# Copyright 2019-2025 SURF.
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
