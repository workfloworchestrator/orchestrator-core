# Copyright 2019-2025 SURF, GÉANT.
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

import types
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from orchestrator.config.assignee import Assignee
from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.schemas.engine_settings import EngineSettingsSchema, GlobalStatusEnum
from orchestrator.schemas.fixed_input import FixedInputSchema
from orchestrator.schemas.process import ProcessBaseSchema
from orchestrator.schemas.product import ProductBaseSchema
from orchestrator.schemas.product_block import ProductBlockSchema
from orchestrator.schemas.resource_type import ResourceTypeSchema
from orchestrator.schemas.search import ProductSchema as SearchProductSchema
from orchestrator.schemas.subscription import SubscriptionSchema
from orchestrator.schemas.subscription_descriptions import SubscriptionDescriptionSchema
from orchestrator.schemas.workflow import WorkflowSchema
from orchestrator.targets import Target
from orchestrator.types import SubscriptionLifecycle
from orchestrator.workflow import ProcessStatus

NOW = datetime.now(tz=timezone.utc)


class TestWorkflowSchemaFromAttributes:
    def _make_orm_obj(self, **overrides: object) -> types.SimpleNamespace:
        data = {
            "workflow_id": uuid4(),
            "name": "create_subscription",
            "target": Target.CREATE,
            "is_task": False,
            "description": None,
            "created_at": NOW,
            "steps": None,
        }
        data.update(overrides)
        return types.SimpleNamespace(**data)

    def test_valid_orm_object_succeeds(self) -> None:
        obj = self._make_orm_obj()
        schema = WorkflowSchema.model_validate(obj, from_attributes=True)
        assert isinstance(schema.workflow_id, UUID)
        assert schema.name == "create_subscription"
        assert schema.target == Target.CREATE

    def test_with_description_succeeds(self) -> None:
        obj = self._make_orm_obj(description="Creates a subscription")
        schema = WorkflowSchema.model_validate(obj, from_attributes=True)
        assert schema.description == "Creates a subscription"

    def test_with_steps_succeeds(self) -> None:
        step_obj = types.SimpleNamespace(name="step_a")
        obj = self._make_orm_obj(steps=[step_obj])
        schema = WorkflowSchema.model_validate(obj, from_attributes=True)
        assert schema.steps is not None
        assert schema.steps[0].name == "step_a"

    def test_missing_required_workflow_id_raises(self) -> None:
        obj = types.SimpleNamespace(
            name="wf",
            target=Target.CREATE,
            is_task=False,
            created_at=NOW,
        )
        with pytest.raises(ValidationError):
            WorkflowSchema.model_validate(obj, from_attributes=True)


class TestProductBlockSchemaFromAttributes:
    def _make_orm_obj(self, **overrides: object) -> types.SimpleNamespace:
        data = {
            "product_block_id": uuid4(),
            "name": "SomeBlock",
            "description": "A product block",
            "tag": "SB",
            "status": ProductLifecycle.ACTIVE,
            "created_at": NOW,
            "end_date": None,
            "resource_types": None,
        }
        data.update(overrides)
        return types.SimpleNamespace(**data)

    def test_valid_orm_object_succeeds(self) -> None:
        obj = self._make_orm_obj()
        schema = ProductBlockSchema.model_validate(obj, from_attributes=True)
        assert isinstance(schema.product_block_id, UUID)
        assert schema.name == "SomeBlock"
        assert schema.status == ProductLifecycle.ACTIVE

    def test_with_end_date_succeeds(self) -> None:
        obj = self._make_orm_obj(end_date=NOW)
        schema = ProductBlockSchema.model_validate(obj, from_attributes=True)
        assert isinstance(schema.end_date, datetime)

    def test_with_resource_types_succeeds(self) -> None:
        rt_obj = types.SimpleNamespace(resource_type_id=uuid4(), resource_type="rt_name", description=None)
        obj = self._make_orm_obj(resource_types=[rt_obj])
        schema = ProductBlockSchema.model_validate(obj, from_attributes=True)
        assert schema.resource_types is not None
        assert len(schema.resource_types) == 1
        assert schema.resource_types[0].resource_type == "rt_name"

    def test_missing_required_product_block_id_raises(self) -> None:
        obj = types.SimpleNamespace(
            name="block",
            description="desc",
            tag="B",
            status=ProductLifecycle.ACTIVE,
            created_at=NOW,
        )
        with pytest.raises(ValidationError):
            ProductBlockSchema.model_validate(obj, from_attributes=True)


class TestProductBaseSchemaFromAttributes:
    def _make_orm_obj(self, **overrides: object) -> types.SimpleNamespace:
        data = {
            "product_id": uuid4(),
            "name": "My Product",
            "description": "Product description",
            "product_type": "Ethernet",
            "tag": "ETH",
            "status": ProductLifecycle.ACTIVE,
            "created_at": NOW,
            "end_date": None,
        }
        data.update(overrides)
        return types.SimpleNamespace(**data)

    def test_valid_orm_object_succeeds(self) -> None:
        obj = self._make_orm_obj()
        schema = ProductBaseSchema.model_validate(obj, from_attributes=True)
        assert isinstance(schema.product_id, UUID)
        assert schema.name == "My Product"
        assert schema.status == ProductLifecycle.ACTIVE

    def test_with_end_date_succeeds(self) -> None:
        obj = self._make_orm_obj(end_date=NOW)
        schema = ProductBaseSchema.model_validate(obj, from_attributes=True)
        assert isinstance(schema.end_date, datetime)

    @pytest.mark.parametrize(
        "status",
        [
            ProductLifecycle.ACTIVE,
            ProductLifecycle.PRE_PRODUCTION,
            ProductLifecycle.PHASE_OUT,
            ProductLifecycle.END_OF_LIFE,
        ],
        ids=["active", "pre_production", "phase_out", "end_of_life"],
    )
    def test_all_lifecycle_statuses_succeed(self, status: ProductLifecycle) -> None:
        obj = self._make_orm_obj(status=status)
        schema = ProductBaseSchema.model_validate(obj, from_attributes=True)
        assert schema.status == status

    def test_missing_required_name_raises(self) -> None:
        obj = types.SimpleNamespace(
            product_id=uuid4(),
            description="desc",
            product_type="Type",
            tag="T",
            status=ProductLifecycle.ACTIVE,
        )
        with pytest.raises(ValidationError):
            ProductBaseSchema.model_validate(obj, from_attributes=True)


class TestResourceTypeSchemaFromAttributes:
    def _make_orm_obj(self, **overrides: object) -> types.SimpleNamespace:
        data = {
            "resource_type_id": uuid4(),
            "resource_type": "vlan",
            "description": "VLAN resource type",
        }
        data.update(overrides)
        return types.SimpleNamespace(**data)

    def test_valid_orm_object_succeeds(self) -> None:
        obj = self._make_orm_obj()
        schema = ResourceTypeSchema.model_validate(obj, from_attributes=True)
        assert isinstance(schema.resource_type_id, UUID)
        assert schema.resource_type == "vlan"

    def test_description_none_succeeds(self) -> None:
        obj = self._make_orm_obj(description=None)
        schema = ResourceTypeSchema.model_validate(obj, from_attributes=True)
        assert schema.description is None

    def test_missing_resource_type_id_raises(self) -> None:
        obj = types.SimpleNamespace(resource_type="rt", description=None)
        with pytest.raises(ValidationError):
            ResourceTypeSchema.model_validate(obj, from_attributes=True)

    def test_missing_resource_type_raises(self) -> None:
        obj = types.SimpleNamespace(resource_type_id=uuid4(), description=None)
        with pytest.raises(ValidationError):
            ResourceTypeSchema.model_validate(obj, from_attributes=True)


class TestSearchProductSchemaFromAttributes:
    def _make_orm_obj(self, **overrides: object) -> types.SimpleNamespace:
        data: dict[str, object] = {
            "name": "Search Product",
            "tag": "SP",
            "product_type": "L2VPN",
        }
        data.update(overrides)
        return types.SimpleNamespace(**data)

    def test_valid_orm_object_succeeds(self) -> None:
        obj = self._make_orm_obj()
        schema = SearchProductSchema.model_validate(obj, from_attributes=True)
        assert schema.name == "Search Product"
        assert schema.tag == "SP"
        assert schema.product_type == "L2VPN"

    @pytest.mark.parametrize(
        "missing_field",
        ["name", "tag", "product_type"],
        ids=["missing_name", "missing_tag", "missing_product_type"],
    )
    def test_missing_required_field_raises(self, missing_field: str) -> None:
        data = {"name": "P", "tag": "T", "product_type": "Type"}
        del data[missing_field]
        obj = types.SimpleNamespace(**data)
        with pytest.raises(ValidationError):
            SearchProductSchema.model_validate(obj, from_attributes=True)


class TestProcessBaseSchemaFromAttributes:
    def _make_orm_obj(self, **overrides: object) -> types.SimpleNamespace:
        data = {
            "process_id": uuid4(),
            "workflow_id": uuid4(),
            "workflow_name": "create_subscription",
            "is_task": False,
            "created_by": None,
            "failed_reason": None,
            "started_at": NOW,
            "last_status": ProcessStatus.RUNNING,
            "last_step": None,
            "assignee": Assignee.SYSTEM,
            "last_modified_at": NOW,
            "traceback": None,
        }
        data.update(overrides)
        return types.SimpleNamespace(**data)

    def test_valid_orm_object_succeeds(self) -> None:
        obj = self._make_orm_obj()
        schema = ProcessBaseSchema.model_validate(obj, from_attributes=True)
        assert isinstance(schema.process_id, UUID)
        assert isinstance(schema.workflow_id, UUID)
        assert schema.workflow_name == "create_subscription"
        assert schema.last_status == ProcessStatus.RUNNING

    def test_with_optional_fields_set_succeeds(self) -> None:
        obj = self._make_orm_obj(
            created_by="user@example.com",
            last_step="Start",
            traceback="Traceback: ...",
        )
        schema = ProcessBaseSchema.model_validate(obj, from_attributes=True)
        assert schema.created_by == "user@example.com"
        assert schema.last_step == "Start"
        assert schema.traceback == "Traceback: ..."

    @pytest.mark.parametrize(
        "status",
        [ProcessStatus.RUNNING, ProcessStatus.FAILED, ProcessStatus.COMPLETED, ProcessStatus.SUSPENDED],
        ids=["running", "failed", "completed", "suspended"],
    )
    def test_all_process_statuses_succeed(self, status: ProcessStatus) -> None:
        obj = self._make_orm_obj(last_status=status)
        schema = ProcessBaseSchema.model_validate(obj, from_attributes=True)
        assert schema.last_status == status

    def test_missing_process_id_raises(self) -> None:
        obj = types.SimpleNamespace(
            workflow_id=uuid4(),
            workflow_name="wf",
            is_task=False,
            started_at=NOW,
            last_status=ProcessStatus.RUNNING,
            assignee=Assignee.SYSTEM,
            last_modified_at=NOW,
        )
        with pytest.raises(ValidationError):
            ProcessBaseSchema.model_validate(obj, from_attributes=True)


class TestEngineSettingsSchemaFromAttributes:
    def _make_orm_obj(self, **overrides: object) -> types.SimpleNamespace:
        data: dict[str, object] = {
            "global_lock": False,
            "running_processes": 3,
            "global_status": None,
        }
        data.update(overrides)
        return types.SimpleNamespace(**data)

    def test_valid_orm_object_succeeds(self) -> None:
        obj = self._make_orm_obj()
        schema = EngineSettingsSchema.model_validate(obj, from_attributes=True)
        assert schema.global_lock is False
        assert schema.running_processes == 3
        assert schema.global_status is None

    def test_with_global_status_succeeds(self) -> None:
        obj = self._make_orm_obj(global_lock=True, global_status=GlobalStatusEnum.RUNNING)
        schema = EngineSettingsSchema.model_validate(obj, from_attributes=True)
        assert schema.global_lock is True
        assert schema.global_status == GlobalStatusEnum.RUNNING

    @pytest.mark.parametrize(
        "status",
        [GlobalStatusEnum.RUNNING, GlobalStatusEnum.PAUSED, GlobalStatusEnum.PAUSING],
        ids=["running", "paused", "pausing"],
    )
    def test_all_global_statuses_succeed(self, status: GlobalStatusEnum) -> None:
        obj = self._make_orm_obj(global_status=status)
        schema = EngineSettingsSchema.model_validate(obj, from_attributes=True)
        assert schema.global_status == status

    def test_missing_running_processes_raises(self) -> None:
        obj = types.SimpleNamespace(global_lock=False)
        with pytest.raises(ValidationError):
            EngineSettingsSchema.model_validate(obj, from_attributes=True)


class TestFixedInputSchemaFromAttributes:
    def _make_orm_obj(self, **overrides: object) -> types.SimpleNamespace:
        data = {
            "fixed_input_id": uuid4(),
            "name": "speed",
            "value": "1000",
            "created_at": NOW,
            "product_id": uuid4(),
        }
        data.update(overrides)
        return types.SimpleNamespace(**data)

    def test_valid_orm_object_succeeds(self) -> None:
        obj = self._make_orm_obj()
        schema = FixedInputSchema.model_validate(obj, from_attributes=True)
        assert isinstance(schema.fixed_input_id, UUID)
        assert schema.name == "speed"
        assert schema.value == "1000"
        assert isinstance(schema.product_id, UUID)

    def test_missing_fixed_input_id_raises(self) -> None:
        obj = types.SimpleNamespace(name="speed", value="1000", created_at=NOW, product_id=uuid4())
        with pytest.raises(ValidationError):
            FixedInputSchema.model_validate(obj, from_attributes=True)

    def test_missing_product_id_raises(self) -> None:
        obj = types.SimpleNamespace(fixed_input_id=uuid4(), name="speed", value="1000", created_at=NOW)
        with pytest.raises(ValidationError):
            FixedInputSchema.model_validate(obj, from_attributes=True)

    def test_created_at_is_datetime(self) -> None:
        obj = self._make_orm_obj()
        schema = FixedInputSchema.model_validate(obj, from_attributes=True)
        assert isinstance(schema.created_at, datetime)


class TestSubscriptionSchemaFromAttributes:
    def _make_orm_obj(self, **overrides: object) -> types.SimpleNamespace:
        data = {
            "subscription_id": uuid4(),
            "start_date": NOW,
            "description": "Test subscription",
            "status": SubscriptionLifecycle.ACTIVE,
            "product_id": uuid4(),
            "customer_id": "customer-123",
            "insync": True,
            "note": None,
            "name": None,
            "end_date": None,
            "product": None,
            "customer_descriptions": None,
            "tag": None,
            "version": 1,
        }
        data.update(overrides)
        return types.SimpleNamespace(**data)

    def test_valid_orm_object_succeeds(self) -> None:
        obj = self._make_orm_obj()
        schema = SubscriptionSchema.model_validate(obj, from_attributes=True)
        assert isinstance(schema.subscription_id, UUID)
        assert schema.description == "Test subscription"
        assert schema.status == SubscriptionLifecycle.ACTIVE
        assert schema.version == 1

    def test_with_name_and_tag_succeeds(self) -> None:
        obj = self._make_orm_obj(name="My Sub", tag="MYSUB")
        schema = SubscriptionSchema.model_validate(obj, from_attributes=True)
        assert schema.name == "My Sub"
        assert schema.tag == "MYSUB"

    def test_with_end_date_succeeds(self) -> None:
        obj = self._make_orm_obj(end_date=NOW)
        schema = SubscriptionSchema.model_validate(obj, from_attributes=True)
        assert isinstance(schema.end_date, datetime)

    @pytest.mark.parametrize(
        "status",
        [SubscriptionLifecycle.INITIAL, SubscriptionLifecycle.ACTIVE, SubscriptionLifecycle.TERMINATED],
        ids=["initial", "active", "terminated"],
    )
    def test_all_subscription_lifecycles_succeed(self, status: SubscriptionLifecycle) -> None:
        obj = self._make_orm_obj(status=status)
        schema = SubscriptionSchema.model_validate(obj, from_attributes=True)
        assert schema.status == status

    def test_missing_subscription_id_raises(self) -> None:
        obj = types.SimpleNamespace(
            description="desc",
            status=SubscriptionLifecycle.ACTIVE,
            customer_id="cust",
            insync=True,
            version=1,
        )
        with pytest.raises(ValidationError):
            SubscriptionSchema.model_validate(obj, from_attributes=True)


class TestSubscriptionDescriptionSchemaFromAttributes:
    def _make_orm_obj(self, **overrides: object) -> types.SimpleNamespace:
        data = {
            "id": uuid4(),
            "description": "Customer description",
            "customer_id": "customer-456",
            "subscription_id": uuid4(),
            "created_at": NOW,
            "version": 1,
        }
        data.update(overrides)
        return types.SimpleNamespace(**data)

    def test_valid_orm_object_succeeds(self) -> None:
        obj = self._make_orm_obj()
        schema = SubscriptionDescriptionSchema.model_validate(obj, from_attributes=True)
        assert isinstance(schema.id, UUID)
        assert schema.description == "Customer description"
        assert isinstance(schema.subscription_id, UUID)
        assert schema.version == 1

    def test_created_at_none_succeeds(self) -> None:
        obj = self._make_orm_obj(created_at=None)
        schema = SubscriptionDescriptionSchema.model_validate(obj, from_attributes=True)
        assert schema.created_at is None

    def test_created_at_is_datetime_when_set(self) -> None:
        obj = self._make_orm_obj(created_at=NOW)
        schema = SubscriptionDescriptionSchema.model_validate(obj, from_attributes=True)
        assert isinstance(schema.created_at, datetime)

    def test_missing_id_raises(self) -> None:
        obj = types.SimpleNamespace(
            description="desc",
            customer_id="cust",
            subscription_id=uuid4(),
            version=1,
        )
        with pytest.raises(ValidationError):
            SubscriptionDescriptionSchema.model_validate(obj, from_attributes=True)

    def test_missing_subscription_id_raises(self) -> None:
        obj = types.SimpleNamespace(
            id=uuid4(),
            description="desc",
            customer_id="cust",
            version=1,
        )
        with pytest.raises(ValidationError):
            SubscriptionDescriptionSchema.model_validate(obj, from_attributes=True)
