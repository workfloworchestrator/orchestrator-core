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

import pytest
from pydantic import ValidationError

from orchestrator.schemas.engine_settings import (
    EngineSettingsBaseSchema,
    EngineSettingsSchema,
    GlobalStatusEnum,
    WorkerStatus,
)


class TestGlobalStatusEnum:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("RUNNING", GlobalStatusEnum.RUNNING),
            ("PAUSED", GlobalStatusEnum.PAUSED),
            ("PAUSING", GlobalStatusEnum.PAUSING),
        ],
        ids=["running", "paused", "pausing"],
    )
    def test_enum_values_are_correct(self, value: str, expected: GlobalStatusEnum) -> None:
        assert GlobalStatusEnum(value) == expected

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            GlobalStatusEnum("STOPPED")


class TestEngineSettingsBaseSchema:
    def test_instantiate_with_global_lock_true_succeeds(self) -> None:
        schema = EngineSettingsBaseSchema(global_lock=True)
        assert schema.global_lock is True

    def test_instantiate_with_global_lock_false_succeeds(self) -> None:
        schema = EngineSettingsBaseSchema(global_lock=False)
        assert schema.global_lock is False

    def test_instantiate_missing_global_lock_raises(self) -> None:
        with pytest.raises(ValidationError):
            EngineSettingsBaseSchema()  # type: ignore[call-arg]


class TestWorkerStatus:
    def test_instantiate_with_executor_type_only_succeeds(self) -> None:
        schema = WorkerStatus(executor_type="threadpool")
        assert schema.executor_type == "threadpool"
        assert schema.number_of_workers_online == 0
        assert schema.number_of_queued_jobs == 0
        assert schema.number_of_running_jobs == 0

    def test_instantiate_with_all_fields(self) -> None:
        schema = WorkerStatus(
            executor_type="celery",
            number_of_workers_online=4,
            number_of_queued_jobs=10,
            number_of_running_jobs=2,
        )
        assert schema.number_of_workers_online == 4
        assert schema.number_of_queued_jobs == 10
        assert schema.number_of_running_jobs == 2

    def test_instantiate_missing_executor_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            WorkerStatus()  # type: ignore[call-arg]

    def test_number_of_workers_defaults_to_zero(self) -> None:
        schema = WorkerStatus(executor_type="sync")
        assert schema.number_of_workers_online == 0


class TestEngineSettingsSchema:
    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = EngineSettingsSchema(global_lock=False, running_processes=5)
        assert schema.global_lock is False
        assert schema.running_processes == 5

    def test_global_status_defaults_to_none(self) -> None:
        schema = EngineSettingsSchema(global_lock=True, running_processes=0)
        assert schema.global_status is None

    @pytest.mark.parametrize(
        "status",
        [GlobalStatusEnum.RUNNING, GlobalStatusEnum.PAUSED, GlobalStatusEnum.PAUSING],
        ids=["running", "paused", "pausing"],
    )
    def test_instantiate_with_global_status_succeeds(self, status: GlobalStatusEnum) -> None:
        schema = EngineSettingsSchema(global_lock=False, running_processes=1, global_status=status)
        assert schema.global_status == status

    def test_instantiate_missing_running_processes_raises(self) -> None:
        with pytest.raises(ValidationError):
            EngineSettingsSchema(global_lock=False)  # type: ignore[call-arg]

    def test_inherits_global_lock_from_base(self) -> None:
        schema = EngineSettingsSchema(global_lock=True, running_processes=3)
        assert schema.global_lock is True
