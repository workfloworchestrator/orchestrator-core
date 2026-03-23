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
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from orchestrator.db.models import DESCRIPTION_LENGTH
from orchestrator.schemas.workflow import (
    StepSchema,
    SubscriptionWorkflowListsSchema,
    WorkflowBaseSchema,
    WorkflowListItemSchema,
    WorkflowPatchSchema,
    WorkflowSchema,
)
from orchestrator.targets import Target

WORKFLOW_ID = uuid4()
NOW = datetime.now(tz=timezone.utc)


def make_workflow_base_data(**overrides) -> dict:
    return {
        "name": "create_subscription",
        "target": Target.CREATE,
        **overrides,
    }


class TestWorkflowBaseSchema:
    @pytest.mark.parametrize(
        "target",
        [Target.CREATE, Target.MODIFY, Target.TERMINATE, Target.SYSTEM, Target.VALIDATE, Target.RECONCILE],
        ids=["create", "modify", "terminate", "system", "validate", "reconcile"],
    )
    def test_instantiate_all_targets_succeeds(self, target: Target) -> None:
        schema = WorkflowBaseSchema(**make_workflow_base_data(target=target))
        assert schema.target == target

    def test_is_task_defaults_to_false(self) -> None:
        schema = WorkflowBaseSchema(**make_workflow_base_data())
        assert schema.is_task is False

    def test_optional_fields_default_to_none(self) -> None:
        schema = WorkflowBaseSchema(**make_workflow_base_data())
        assert schema.description is None
        assert schema.created_at is None

    def test_instantiate_with_all_fields(self) -> None:
        schema = WorkflowBaseSchema(
            name="modify_subscription",
            target=Target.MODIFY,
            is_task=True,
            description="Modify a subscription",
            created_at=NOW,
        )
        assert schema.is_task is True
        assert schema.description == "Modify a subscription"
        assert isinstance(schema.created_at, datetime)

    def test_instantiate_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            WorkflowBaseSchema(target=Target.CREATE)  # type: ignore[call-arg]

    def test_instantiate_missing_target_raises(self) -> None:
        with pytest.raises(ValidationError):
            WorkflowBaseSchema(name="wf")  # type: ignore[call-arg]

    def test_instantiate_invalid_target_raises(self) -> None:
        with pytest.raises(ValidationError):
            WorkflowBaseSchema(name="wf", target="INVALID")  # type: ignore[arg-type]


class TestStepSchema:
    def test_instantiate_valid_name_succeeds(self) -> None:
        schema = StepSchema(name="step_1")
        assert schema.name == "step_1"

    def test_instantiate_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            StepSchema()  # type: ignore[call-arg]


class TestWorkflowSchema:
    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = WorkflowSchema(
            **make_workflow_base_data(),
            workflow_id=WORKFLOW_ID,
            created_at=NOW,
        )
        assert schema.workflow_id == WORKFLOW_ID
        assert isinstance(schema.created_at, datetime)

    def test_steps_defaults_to_none(self) -> None:
        schema = WorkflowSchema(
            **make_workflow_base_data(),
            workflow_id=WORKFLOW_ID,
            created_at=NOW,
        )
        assert schema.steps is None

    def test_instantiate_with_steps(self) -> None:
        schema = WorkflowSchema(
            **make_workflow_base_data(),
            workflow_id=WORKFLOW_ID,
            created_at=NOW,
            steps=[StepSchema(name="step_a"), StepSchema(name="step_b")],
        )
        assert schema.steps is not None
        assert len(schema.steps) == 2
        assert schema.steps[0].name == "step_a"

    def test_instantiate_missing_workflow_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            WorkflowSchema(**make_workflow_base_data(), created_at=NOW)

    def test_workflow_id_is_uuid_type(self) -> None:
        schema = WorkflowSchema(
            **make_workflow_base_data(),
            workflow_id=WORKFLOW_ID,
            created_at=NOW,
        )
        assert isinstance(schema.workflow_id, UUID)


class TestWorkflowListItemSchema:
    def test_instantiate_with_name_only_succeeds(self) -> None:
        schema = WorkflowListItemSchema(name="terminate_subscription")
        assert schema.name == "terminate_subscription"

    def test_all_optional_fields_default_to_none(self) -> None:
        schema = WorkflowListItemSchema(name="wf")
        assert schema.description is None
        assert schema.reason is None
        assert schema.usable_when is None
        assert schema.status is None
        assert schema.action is None
        assert schema.locked_relations is None
        assert schema.unterminated_parents is None
        assert schema.unterminated_in_use_by_subscriptions is None

    def test_instantiate_with_locked_relations(self) -> None:
        sub_id = uuid4()
        schema = WorkflowListItemSchema(name="wf", locked_relations=[sub_id])
        assert schema.locked_relations is not None
        assert schema.locked_relations[0] == sub_id

    def test_instantiate_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            WorkflowListItemSchema()  # type: ignore[call-arg]


class TestSubscriptionWorkflowListsSchema:
    def _make_wf_item(self, name: str) -> WorkflowListItemSchema:
        return WorkflowListItemSchema(name=name)

    def test_instantiate_valid_data_succeeds(self) -> None:
        schema = SubscriptionWorkflowListsSchema(
            create=[self._make_wf_item("create_sub")],
            modify=[],
            terminate=[],
            system=[],
            reconcile=[],
        )
        assert len(schema.create) == 1
        assert schema.create[0].name == "create_sub"

    def test_validate_field_defaults_to_empty_list(self) -> None:
        schema = SubscriptionWorkflowListsSchema(
            create=[],
            modify=[],
            terminate=[],
            system=[],
            reconcile=[],
        )
        assert schema.validate_ == []

    def test_validate_field_populated_via_alias(self) -> None:
        schema = SubscriptionWorkflowListsSchema(
            create=[],
            modify=[],
            terminate=[],
            system=[],
            reconcile=[],
            validate=[self._make_wf_item("validate_sub")],
        )
        assert len(schema.validate_) == 1
        assert schema.validate_[0].name == "validate_sub"

    def test_reason_and_locked_relations_are_optional(self) -> None:
        schema = SubscriptionWorkflowListsSchema(
            create=[],
            modify=[],
            terminate=[],
            system=[],
            reconcile=[],
        )
        assert schema.reason is None
        assert schema.locked_relations is None

    def test_instantiate_missing_create_raises(self) -> None:
        with pytest.raises(ValidationError):
            SubscriptionWorkflowListsSchema(  # type: ignore[call-arg]
                modify=[],
                terminate=[],
                system=[],
                reconcile=[],
            )


class TestWorkflowPatchSchema:
    def test_instantiate_with_description_succeeds(self) -> None:
        schema = WorkflowPatchSchema(description="Updated description")
        assert schema.description == "Updated description"

    def test_instantiate_without_description_defaults_to_none(self) -> None:
        schema = WorkflowPatchSchema()
        assert schema.description is None

    def test_description_at_max_length_succeeds(self) -> None:
        description = "d" * DESCRIPTION_LENGTH
        schema = WorkflowPatchSchema(description=description)
        assert schema.description is not None
        assert len(schema.description) == DESCRIPTION_LENGTH

    def test_description_exceeding_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            WorkflowPatchSchema(description="x" * (DESCRIPTION_LENGTH + 1))
