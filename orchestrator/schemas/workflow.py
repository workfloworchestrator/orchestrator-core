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

from orchestrator.schemas.base import OrchestratorBaseModel
from orchestrator.targets import Target


class WorkflowBaseSchema(OrchestratorBaseModel):
    name: str
    target: Target
    description: Optional[str]
    created_at: Optional[datetime]


class WorkflowSchema(WorkflowBaseSchema):
    workflow_id: UUID
    created_at: datetime

    class Config:
        orm_mode = True


class WorkflowWithProductTagsSchema(WorkflowBaseSchema):
    product_tags: List[str]


class WorkflowListItemSchema(OrchestratorBaseModel):
    name: str
    description: Optional[str]
    reason: Optional[str]
    usable_when: Optional[List[Any]]
    status: Optional[str]
    action: Optional[str]
    locked_relations: Optional[List[UUID]]
    unterminated_parents: Optional[List[UUID]]
    unterminated_in_use_by_subscriptions: Optional[List[UUID]]


class SubscriptionWorkflowListsSchema(OrchestratorBaseModel):
    reason: Optional[str]
    locked_relations: Optional[List[UUID]]
    create: List[WorkflowListItemSchema]
    modify: List[WorkflowListItemSchema]
    terminate: List[WorkflowListItemSchema]
    system: List[WorkflowListItemSchema]
