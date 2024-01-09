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

from pydantic import ConfigDict

from orchestrator.schemas.base import OrchestratorBaseModel
from orchestrator.targets import Target


class WorkflowBaseSchema(OrchestratorBaseModel):
    name: str
    target: Target
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class StepSchema(OrchestratorBaseModel):
    name: str


class WorkflowSchema(WorkflowBaseSchema):
    workflow_id: UUID
    created_at: datetime
    steps: Optional[List[StepSchema]] = None

    model_config = ConfigDict(from_attributes=True)


class WorkflowWithProductTagsSchema(WorkflowBaseSchema):
    product_tags: List[str]


class WorkflowListItemSchema(OrchestratorBaseModel):
    name: str
    description: Optional[str] = None
    reason: Optional[str] = None
    usable_when: Optional[List[Any]] = None
    status: Optional[str] = None
    action: Optional[str] = None
    locked_relations: Optional[List[UUID]] = None
    unterminated_parents: Optional[List[UUID]] = None
    unterminated_in_use_by_subscriptions: Optional[List[UUID]] = None


class SubscriptionWorkflowListsSchema(OrchestratorBaseModel):
    reason: Optional[str] = None
    locked_relations: Optional[List[UUID]] = None
    create: List[WorkflowListItemSchema]
    modify: List[WorkflowListItemSchema]
    terminate: List[WorkflowListItemSchema]
    system: List[WorkflowListItemSchema]
