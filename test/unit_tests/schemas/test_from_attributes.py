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

"""Tests that all major schemas support model_validate(obj, from_attributes=True) with ORM-like objects."""

import types
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from orchestrator.config.assignee import Assignee
from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.schemas.engine_settings import EngineSettingsSchema
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

_ORM_FIXTURES: dict[type, dict] = {
    WorkflowSchema: {
        "workflow_id": uuid4(),
        "name": "create_subscription",
        "target": Target.CREATE,
        "is_task": False,
        "description": None,
        "created_at": NOW,
        "steps": None,
    },
    ProductBlockSchema: {
        "product_block_id": uuid4(),
        "name": "SomeBlock",
        "description": "A product block",
        "tag": "SB",
        "status": ProductLifecycle.ACTIVE,
        "created_at": NOW,
        "end_date": None,
        "resource_types": None,
    },
    ProductBaseSchema: {
        "product_id": uuid4(),
        "name": "My Product",
        "description": "Product description",
        "product_type": "Ethernet",
        "tag": "ETH",
        "status": ProductLifecycle.ACTIVE,
        "created_at": NOW,
        "end_date": None,
    },
    ResourceTypeSchema: {
        "resource_type_id": uuid4(),
        "resource_type": "vlan",
        "description": "VLAN resource type",
    },
    SearchProductSchema: {
        "name": "Search Product",
        "tag": "SP",
        "product_type": "L2VPN",
    },
    ProcessBaseSchema: {
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
    },
    EngineSettingsSchema: {
        "global_lock": False,
        "running_processes": 3,
        "global_status": None,
    },
    FixedInputSchema: {
        "fixed_input_id": uuid4(),
        "name": "speed",
        "value": "1000",
        "created_at": NOW,
        "product_id": uuid4(),
    },
    SubscriptionSchema: {
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
    },
    SubscriptionDescriptionSchema: {
        "id": uuid4(),
        "description": "Customer description",
        "customer_id": "customer-456",
        "subscription_id": uuid4(),
        "created_at": NOW,
        "version": 1,
    },
}


@pytest.mark.parametrize(
    "schema_cls",
    [pytest.param(cls, id=cls.__name__) for cls in _ORM_FIXTURES],
)
def test_from_attributes_succeeds(schema_cls: type) -> None:
    obj = types.SimpleNamespace(**_ORM_FIXTURES[schema_cls])
    result = schema_cls.model_validate(obj, from_attributes=True)  # type: ignore[attr-defined]
    assert result is not None


def test_workflow_schema_includes_nested_steps() -> None:
    step_obj = types.SimpleNamespace(name="step_a")
    data = {**_ORM_FIXTURES[WorkflowSchema], "steps": [step_obj]}
    schema = WorkflowSchema.model_validate(types.SimpleNamespace(**data), from_attributes=True)
    assert schema.steps is not None
    assert schema.steps[0].name == "step_a"


def test_product_block_schema_includes_nested_resource_types() -> None:
    rt_obj = types.SimpleNamespace(resource_type_id=uuid4(), resource_type="rt_name", description=None)
    data = {**_ORM_FIXTURES[ProductBlockSchema], "resource_types": [rt_obj]}
    schema = ProductBlockSchema.model_validate(types.SimpleNamespace(**data), from_attributes=True)
    assert schema.resource_types is not None
    assert schema.resource_types[0].resource_type == "rt_name"
