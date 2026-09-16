# Copyright 2019-2026 SURF.
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

from pydantic import ConfigDict, field_validator

from orchestrator.core.config.assignee import Assignee
from orchestrator.core.db.models import SubscriptionTable
from orchestrator.core.schemas.base import OrchestratorBaseModel
from orchestrator.core.targets import Target
from orchestrator.core.workflow import ProcessStatus


class ProcessSubscriptionIndexSchema(OrchestratorBaseModel):
    """Minimal subscription summary embedded in a process's search index entry."""

    subscription_id: UUID
    description: str
    customer_id: str
    product_name: str | None = None
    product_tag: str | None = None

    @classmethod
    def from_subscription(cls, subscription: SubscriptionTable) -> "ProcessSubscriptionIndexSchema":
        """Build a summary from a (possibly app-specific) SubscriptionTable instance."""
        product = subscription.product
        return cls(
            subscription_id=subscription.subscription_id,
            description=subscription.description,
            customer_id=subscription.customer_id,
            product_name=product.name,
            product_tag=product.tag,
        )


class ProcessIndexSchema(OrchestratorBaseModel):
    process_id: UUID
    workflow_id: UUID
    workflow_name: str
    is_task: bool
    created_by: str | None = None
    failed_reason: str | None = None
    started_at: datetime
    last_status: ProcessStatus
    last_step: str | None = None
    assignee: Assignee
    last_modified_at: datetime
    traceback: str | None = None
    model_config = ConfigDict(from_attributes=True)
    workflow_target: Target | None = None
    note: str | None = None
    subscriptions: list[ProcessSubscriptionIndexSchema] = []

    @field_validator("subscriptions", mode="before")
    @classmethod
    def _build_subscriptions(cls, value: Any) -> Any:
        """Map raw ORM subscription instances (e.g. from an association proxy) to summaries."""
        return [
            (
                item
                if isinstance(item, ProcessSubscriptionIndexSchema)
                else ProcessSubscriptionIndexSchema.from_subscription(item)
            )
            for item in value
        ]
