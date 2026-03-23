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

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from orchestrator.schemas.base import OrchestratorBaseModel


class TestOrchestratorBaseModel:
    def test_instantiate_subclass_valid_data_succeeds(self) -> None:
        # Arrange / Act
        class MyModel(OrchestratorBaseModel):
            name: str
            value: int

        instance = MyModel(name="test", value=42)

        # Assert
        assert instance.name == "test"
        assert instance.value == 42

    def test_instantiate_missing_required_field_raises_validation_error(self) -> None:
        # Arrange
        class MyModel(OrchestratorBaseModel):
            name: str

        # Act / Assert
        with pytest.raises(ValidationError):
            MyModel()  # type: ignore[call-arg]

    def test_serialize_datetime_as_timestamp(self) -> None:
        # Arrange
        class MyModel(OrchestratorBaseModel):
            created_at: datetime

        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        instance = MyModel(created_at=dt)

        # Act
        serialized = json.loads(instance.model_dump_json())

        # Assert
        assert serialized["created_at"] == dt.timestamp()

    def test_serialize_datetime_naive_as_timestamp(self) -> None:
        # Arrange
        class MyModel(OrchestratorBaseModel):
            ts: datetime

        dt = datetime(2023, 6, 1, 0, 0, 0)
        instance = MyModel(ts=dt)

        # Act
        serialized = json.loads(instance.model_dump_json())

        # Assert
        assert serialized["ts"] == dt.timestamp()

    def test_model_dump_returns_dict(self) -> None:
        # Arrange
        class MyModel(OrchestratorBaseModel):
            x: int

        instance = MyModel(x=5)

        # Act
        result = instance.model_dump()

        # Assert
        assert isinstance(result, dict)
        assert result["x"] == 5

    def test_inherits_base_model_behavior(self) -> None:
        # Arrange
        class MyModel(OrchestratorBaseModel):
            a: str
            b: int | None = None

        # Act
        instance = MyModel(a="hello")

        # Assert
        assert instance.a == "hello"
        assert instance.b is None
