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

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from orchestrator.config.assignee import Assignee
from orchestrator.schemas.process import (
    ProcessBaseSchema,
    ProcessIdSchema,
    ProcessResumeAllSchema,
    ProcessSchema,
    ProcessStatusCounts,
    ProcessStepSchema,
    Reporter,
)
from orchestrator.targets import Target
from orchestrator.workflow import ProcessStatus

PROCESS_ID = uuid4()
WORKFLOW_ID = uuid4()
NOW = datetime.now(tz=timezone.utc)


def make_process_base_data(**overrides) -> dict:
    return {
        "process_id": str(PROCESS_ID),
        "workflow_id": str(WORKFLOW_ID),
        "workflow_name": "create_something",
        "is_task": False,
        "started_at": NOW.isoformat(),
        "last_status": ProcessStatus.RUNNING,
        "assignee": Assignee.SYSTEM,
        "last_modified_at": NOW.isoformat(),
        **overrides,
    }


class TestProcessIdSchema:
    def test_instantiate_valid_uuid_succeeds(self) -> None:
        schema = ProcessIdSchema(id=PROCESS_ID)
        assert schema.id == PROCESS_ID

    def test_instantiate_missing_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProcessIdSchema()  # type: ignore[call-arg]

    def test_instantiate_invalid_uuid_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProcessIdSchema(id="not-a-uuid")  # type: ignore[arg-type]


class TestProcessBaseSchema:
    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = ProcessBaseSchema(**make_process_base_data())
        assert schema.process_id == PROCESS_ID
        assert schema.workflow_name == "create_something"
        assert schema.is_task is False
        assert schema.assignee == Assignee.SYSTEM

    def test_optional_fields_default_to_none(self) -> None:
        schema = ProcessBaseSchema(**make_process_base_data())
        assert schema.created_by is None
        assert schema.failed_reason is None
        assert schema.last_step is None
        assert schema.traceback is None

    def test_instantiate_with_optional_fields(self) -> None:
        schema = ProcessBaseSchema(
            **make_process_base_data(
                created_by="user@example.com",
                failed_reason="Something failed",
                last_step="step_3",
                traceback="Traceback...",
            )
        )
        assert schema.created_by == "user@example.com"
        assert schema.failed_reason == "Something failed"

    @pytest.mark.parametrize(
        "status",
        [
            ProcessStatus.RUNNING,
            ProcessStatus.FAILED,
            ProcessStatus.COMPLETED,
            ProcessStatus.SUSPENDED,
            ProcessStatus.WAITING,
        ],
        ids=["running", "failed", "completed", "suspended", "waiting"],
    )
    def test_instantiate_valid_process_status_succeeds(self, status: ProcessStatus) -> None:
        schema = ProcessBaseSchema(**make_process_base_data(last_status=status))
        assert schema.last_status == status

    @pytest.mark.parametrize(
        "assignee",
        [Assignee.NOC, Assignee.SYSTEM, Assignee.CHANGES, Assignee.KLANTSUPPORT],
        ids=["noc", "system", "changes", "klantsupport"],
    )
    def test_instantiate_all_assignees_succeeds(self, assignee: Assignee) -> None:
        schema = ProcessBaseSchema(**make_process_base_data(assignee=assignee))
        assert schema.assignee == assignee

    def test_instantiate_missing_required_field_raises(self) -> None:
        data = make_process_base_data()
        del data["workflow_name"]
        with pytest.raises(ValidationError):
            ProcessBaseSchema(**data)

    def test_instantiate_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProcessBaseSchema(**make_process_base_data(last_status="not_a_status"))


class TestProcessStepSchema:
    def test_instantiate_minimal_valid_data_succeeds(self) -> None:
        schema = ProcessStepSchema(name="step_1", status="success")
        assert schema.name == "step_1"
        assert schema.status == "success"

    def test_optional_fields_default_to_none(self) -> None:
        schema = ProcessStepSchema(name="step_1", status="running")
        assert schema.step_id is None
        assert schema.created_by is None
        assert schema.executed is None
        assert schema.started is None
        assert schema.completed is None
        assert schema.commit_hash is None
        assert schema.state is None
        assert schema.state_delta is None

    def test_instantiate_with_all_fields(self) -> None:
        step_id = uuid4()
        schema = ProcessStepSchema(
            step_id=step_id,
            name="step_2",
            status="completed",
            created_by="user",
            started=NOW,
            completed=NOW,
            commit_hash="abc123",
            state={"key": "val"},
            state_delta={"changed": True},
        )
        assert schema.step_id == step_id
        assert schema.commit_hash == "abc123"

    def test_instantiate_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProcessStepSchema(status="success")  # type: ignore[call-arg]

    def test_instantiate_missing_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProcessStepSchema(name="step")  # type: ignore[call-arg]


class TestProcessSchema:
    def test_instantiate_valid_minimal_data_succeeds(self) -> None:
        schema = ProcessSchema(**make_process_base_data(), subscriptions=[])
        assert schema.process_id == PROCESS_ID
        assert schema.subscriptions == []

    def test_optional_fields_default_to_none(self) -> None:
        schema = ProcessSchema(**make_process_base_data(), subscriptions=[])
        assert schema.product_id is None
        assert schema.customer_id is None
        assert schema.workflow_target is None
        assert schema.current_state is None
        assert schema.steps is None
        assert schema.form is None

    @pytest.mark.parametrize(
        "target",
        [Target.CREATE, Target.MODIFY, Target.TERMINATE, Target.SYSTEM, Target.VALIDATE],
        ids=["create", "modify", "terminate", "system", "validate"],
    )
    def test_instantiate_all_workflow_targets_succeeds(self, target: Target) -> None:
        schema = ProcessSchema(**make_process_base_data(workflow_target=target), subscriptions=[])
        assert schema.workflow_target == target

    def test_instantiate_with_steps_succeeds(self) -> None:
        steps = [ProcessStepSchema(name="s1", status="success"), ProcessStepSchema(name="s2", status="running")]
        schema = ProcessSchema(**make_process_base_data(), subscriptions=[], steps=steps)
        assert schema.steps is not None
        assert len(schema.steps) == 2


class TestProcessResumeAllSchema:
    def test_instantiate_valid_count_succeeds(self) -> None:
        schema = ProcessResumeAllSchema(count=5)
        assert schema.count == 5

    def test_instantiate_zero_count_succeeds(self) -> None:
        schema = ProcessResumeAllSchema(count=0)
        assert schema.count == 0

    def test_instantiate_missing_count_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProcessResumeAllSchema()  # type: ignore[call-arg]


class TestProcessStatusCounts:
    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = ProcessStatusCounts(
            process_counts={ProcessStatus.RUNNING: 2, ProcessStatus.FAILED: 1},
            task_counts={ProcessStatus.COMPLETED: 10},
        )
        assert schema.process_counts[ProcessStatus.RUNNING] == 2
        assert schema.task_counts[ProcessStatus.COMPLETED] == 10

    def test_instantiate_empty_counts_succeeds(self) -> None:
        schema = ProcessStatusCounts(process_counts={}, task_counts={})
        assert schema.process_counts == {}
        assert schema.task_counts == {}

    def test_instantiate_missing_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProcessStatusCounts(process_counts={})  # type: ignore[call-arg]


class TestReporter:
    def test_reporter_type_is_annotated_str(self) -> None:
        # Reporter = Annotated[str, Field(max_length=100)]
        # Verify it's usable as a string annotation
        import typing

        origin = typing.get_origin(Reporter)
        assert origin is not None
