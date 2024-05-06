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
from typing import Any
from uuid import UUID

from pydantic import ConfigDict

from orchestrator.schemas.base import OrchestratorBaseModel
from orchestrator.targets import Target


class WorkflowBaseSchema(OrchestratorBaseModel):
    name: str
    target: Target
    description: str | None = None
    created_at: datetime | None = None


class StepSchema(OrchestratorBaseModel):
    name: str


class WorkflowSchema(WorkflowBaseSchema):
    workflow_id: UUID
    created_at: datetime
    steps: list[StepSchema] | None = None

    model_config = ConfigDict(from_attributes=True)


class WorkflowListItemSchema(OrchestratorBaseModel):
    name: str
    description: str | None = None
    reason: str | None = None
    usable_when: list[Any] | None = None
    status: str | None = None
    action: str | None = None
    locked_relations: list[UUID] | None = None
    unterminated_parents: list[UUID] | None = None
    unterminated_in_use_by_subscriptions: list[UUID] | None = None


class SubscriptionWorkflowListsSchema(OrchestratorBaseModel):
    reason: str | None = None
    locked_relations: list[UUID] | None = None
    create: list[WorkflowListItemSchema]
    modify: list[WorkflowListItemSchema]
    terminate: list[WorkflowListItemSchema]
    system: list[WorkflowListItemSchema]
