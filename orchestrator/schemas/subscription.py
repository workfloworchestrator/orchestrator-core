# Copyright 2019-2020 SURF.
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

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import ConfigDict, Field

from orchestrator.schemas.base import OrchestratorBaseModel
from orchestrator.schemas.product import ProductBaseSchema
from orchestrator.schemas.product_block import ProductBlockSchema
from orchestrator.schemas.resource_type import ResourceTypeSchema
from orchestrator.schemas.subscription_descriptions import SubscriptionDescriptionSchema
from orchestrator.types import SubscriptionLifecycle, strEnum


class PortMode(strEnum):
    """Valid port modes."""

    TAGGED = "tagged"
    UNTAGGED = "untagged"
    LINKMEMBER = "link_member"


class SubscriptionRelationSchema(OrchestratorBaseModel):
    domain_model_attr: Optional[str] = None
    parent_id: UUID
    child_id: UUID
    in_use_by_id: UUID
    depends_on_id: UUID
    order_id: int
    model_config = ConfigDict(from_attributes=True)


class SubscriptionInstanceValueBaseSchema(OrchestratorBaseModel):
    resource_type_id: UUID
    subscription_instance_id: UUID
    subscription_instance_value_id: UUID
    value: str
    resource_type: ResourceTypeSchema
    model_config = ConfigDict(from_attributes=True)


class SubscriptionInstanceBase(OrchestratorBaseModel):
    label: Optional[str] = None
    subscription_id: UUID
    product_block_id: UUID
    subscription_instance_id: UUID
    values: List[SubscriptionInstanceValueBaseSchema]
    parent_relations: List[SubscriptionRelationSchema]
    children_relations: List[SubscriptionRelationSchema]
    in_use_by_block_relations: List[SubscriptionRelationSchema]
    depends_on_block_relations: List[SubscriptionRelationSchema]
    product_block: ProductBlockSchema
    model_config = ConfigDict(from_attributes=True)


class SubscriptionBaseSchema(OrchestratorBaseModel):
    subscription_id: Optional[UUID] = None
    start_date: Optional[datetime] = None
    description: str
    status: SubscriptionLifecycle
    product_id: Optional[UUID] = None
    customer_id: str
    insync: bool
    note: Optional[str] = None


class SubscriptionSchema(SubscriptionBaseSchema):
    name: Optional[str] = None
    subscription_id: UUID
    end_date: Optional[datetime] = None
    product: Optional[ProductBaseSchema] = None
    customer_descriptions: Optional[List[SubscriptionDescriptionSchema]] = None
    tag: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class SubscriptionWithMetadata(SubscriptionSchema):
    metadata_: Optional[Any] = Field(..., alias="metadata")


class SubscriptionIdSchema(OrchestratorBaseModel):
    subscription_id: UUID


class SubscriptionDomainModelSchema(SubscriptionSchema):
    customer_descriptions: List[Optional[SubscriptionDescriptionSchema]] = []  # type: ignore
    product: ProductBaseSchema
    model_config = ConfigDict(extra="allow")
