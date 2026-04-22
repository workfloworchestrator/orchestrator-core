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

"""Tests for OrchestratorBaseModel custom datetime-to-timestamp JSON serialization."""

import json
from datetime import datetime, timezone

import pytest

from orchestrator.core.schemas.base import OrchestratorBaseModel


class _DateTimeModel(OrchestratorBaseModel):
    ts: datetime


@pytest.mark.parametrize(
    "dt",
    [
        pytest.param(datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc), id="aware-utc"),
        pytest.param(datetime(2023, 6, 1, 0, 0, 0), id="naive"),
    ],
)
def test_json_serializes_datetime_as_unix_timestamp(dt: datetime) -> None:
    serialized = json.loads(_DateTimeModel(ts=dt).model_dump_json())
    assert serialized["ts"] == dt.timestamp()
