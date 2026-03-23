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

from uuid import uuid4

import pytest
from pydantic import ValidationError

from orchestrator.schemas.schedules import (
    APSchedulerJobCreate,
    APSchedulerJobDelete,
    APSchedulerJobUpdate,
    APSJobAdapter,
)

WORKFLOW_ID = uuid4()
SCHEDULE_ID = uuid4()


class TestAPSchedulerJobCreate:
    def test_instantiate_minimal_valid_data_succeeds(self) -> None:
        schema = APSchedulerJobCreate(
            workflow_name="create_sub",
            workflow_id=WORKFLOW_ID,
            trigger="interval",
        )
        assert schema.workflow_name == "create_sub"
        assert schema.workflow_id == WORKFLOW_ID
        assert schema.trigger == "interval"
        assert schema.scheduled_type == "create"

    def test_trigger_kwargs_defaults_to_empty_dict(self) -> None:
        schema = APSchedulerJobCreate(
            workflow_name="wf",
            workflow_id=WORKFLOW_ID,
            trigger="cron",
        )
        assert schema.trigger_kwargs == {}

    def test_user_inputs_defaults_to_empty_list(self) -> None:
        schema = APSchedulerJobCreate(
            workflow_name="wf",
            workflow_id=WORKFLOW_ID,
            trigger="date",
        )
        assert schema.user_inputs == []

    def test_name_defaults_to_none(self) -> None:
        schema = APSchedulerJobCreate(
            workflow_name="wf",
            workflow_id=WORKFLOW_ID,
            trigger="interval",
        )
        assert schema.name is None

    def test_instantiate_with_name_and_inputs(self) -> None:
        schema = APSchedulerJobCreate(
            name="my_job",
            workflow_name="wf",
            workflow_id=WORKFLOW_ID,
            trigger="interval",
            trigger_kwargs={"seconds": 30},
            user_inputs=[{"key": "value"}],
        )
        assert schema.name == "my_job"
        assert schema.trigger_kwargs == {"seconds": 30}
        assert schema.user_inputs == [{"key": "value"}]

    @pytest.mark.parametrize("trigger", ["interval", "cron", "date"], ids=["interval", "cron", "date"])
    def test_valid_trigger_values_succeed(self, trigger: str) -> None:
        schema = APSchedulerJobCreate(
            workflow_name="wf",
            workflow_id=WORKFLOW_ID,
            trigger=trigger,  # type: ignore[arg-type]
        )
        assert schema.trigger == trigger

    def test_invalid_trigger_raises(self) -> None:
        with pytest.raises(ValidationError):
            APSchedulerJobCreate(
                workflow_name="wf",
                workflow_id=WORKFLOW_ID,
                trigger="unknown",  # type: ignore[arg-type]
            )

    def test_scheduled_type_is_frozen_as_create(self) -> None:
        schema = APSchedulerJobCreate(
            workflow_name="wf",
            workflow_id=WORKFLOW_ID,
            trigger="interval",
        )
        assert schema.scheduled_type == "create"

    def test_missing_workflow_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            APSchedulerJobCreate(  # type: ignore[call-arg]
                workflow_id=WORKFLOW_ID,
                trigger="interval",
            )

    def test_missing_workflow_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            APSchedulerJobCreate(  # type: ignore[call-arg]
                workflow_name="wf",
                trigger="interval",
            )

    def test_missing_trigger_raises(self) -> None:
        with pytest.raises(ValidationError):
            APSchedulerJobCreate(  # type: ignore[call-arg]
                workflow_name="wf",
                workflow_id=WORKFLOW_ID,
            )


class TestAPSchedulerJobUpdate:
    def test_instantiate_minimal_valid_data_succeeds(self) -> None:
        schema = APSchedulerJobUpdate(schedule_id=SCHEDULE_ID)
        assert schema.schedule_id == SCHEDULE_ID
        assert schema.scheduled_type == "update"

    def test_optional_fields_default_to_none(self) -> None:
        schema = APSchedulerJobUpdate(schedule_id=SCHEDULE_ID)
        assert schema.name is None
        assert schema.trigger is None
        assert schema.trigger_kwargs is None

    def test_instantiate_with_trigger_update(self) -> None:
        schema = APSchedulerJobUpdate(
            schedule_id=SCHEDULE_ID,
            trigger="cron",
            trigger_kwargs={"hour": 1},
        )
        assert schema.trigger == "cron"
        assert schema.trigger_kwargs == {"hour": 1}

    def test_missing_schedule_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            APSchedulerJobUpdate()  # type: ignore[call-arg]

    def test_scheduled_type_is_update(self) -> None:
        schema = APSchedulerJobUpdate(schedule_id=SCHEDULE_ID)
        assert schema.scheduled_type == "update"


class TestAPSchedulerJobDelete:
    def test_instantiate_minimal_valid_data_succeeds(self) -> None:
        schema = APSchedulerJobDelete(workflow_id=WORKFLOW_ID)
        assert schema.workflow_id == WORKFLOW_ID
        assert schema.scheduled_type == "delete"

    def test_schedule_id_defaults_to_none(self) -> None:
        schema = APSchedulerJobDelete(workflow_id=WORKFLOW_ID)
        assert schema.schedule_id is None

    def test_instantiate_with_schedule_id(self) -> None:
        schema = APSchedulerJobDelete(workflow_id=WORKFLOW_ID, schedule_id=SCHEDULE_ID)
        assert schema.schedule_id == SCHEDULE_ID

    def test_missing_workflow_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            APSchedulerJobDelete()  # type: ignore[call-arg]

    def test_scheduled_type_is_delete(self) -> None:
        schema = APSchedulerJobDelete(workflow_id=WORKFLOW_ID)
        assert schema.scheduled_type == "delete"


class TestAPSJobAdapter:
    def test_adapter_validates_create_job(self) -> None:
        data = {
            "scheduled_type": "create",
            "workflow_name": "wf",
            "workflow_id": str(WORKFLOW_ID),
            "trigger": "interval",
        }
        job = APSJobAdapter.validate_python(data)
        assert isinstance(job, APSchedulerJobCreate)

    def test_adapter_validates_update_job(self) -> None:
        data = {
            "scheduled_type": "update",
            "schedule_id": str(SCHEDULE_ID),
        }
        job = APSJobAdapter.validate_python(data)
        assert isinstance(job, APSchedulerJobUpdate)

    def test_adapter_validates_delete_job(self) -> None:
        data = {
            "scheduled_type": "delete",
            "workflow_id": str(WORKFLOW_ID),
        }
        job = APSJobAdapter.validate_python(data)
        assert isinstance(job, APSchedulerJobDelete)

    def test_adapter_invalid_discriminator_raises(self) -> None:
        data = {
            "scheduled_type": "unknown",
        }
        with pytest.raises(ValidationError):
            APSJobAdapter.validate_python(data)

    def test_adapter_missing_discriminator_raises(self) -> None:
        data = {"workflow_name": "wf"}
        with pytest.raises(ValidationError):
            APSJobAdapter.validate_python(data)
