# Copyright 2019-2026 SURF, SURF.
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

from orchestrator.search.core.types import EntityType

DEFAULT_RESPONSE_COLUMNS: dict[EntityType, list[str]] = {
    EntityType.SUBSCRIPTION: [
        "subscription.description",
        "subscription.status",
        "subscription.insync",
        "subscription.start_date",
        "subscription.product.name",
        "subscription.product.tag",
        "subscription.customer_id",
    ],
    EntityType.PROCESS: [
        "process.workflow_name",
        "process.last_status",
        "process.assignee",
        "process.started_at",
        "process.last_modified_at",
        "process.created_by",
        "process.is_task",
    ],
    EntityType.WORKFLOW: [
        "workflow.name",
        "workflow.description",
        "workflow.target",
    ],
    EntityType.PRODUCT: [
        "product.name",
        "product.description",
        "product.product_type",
        "product.status",
        "product.tag",
    ],
}
