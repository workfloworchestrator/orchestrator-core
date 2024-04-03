# Copyright 2019-2023 SURF.
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

from uuid import UUID

import structlog
from sqlalchemy import BinaryExpression, ColumnElement, false, select

from orchestrator.db import ProcessSubscriptionTable, ProcessTable, ProductTable, SubscriptionTable, WorkflowTable
from orchestrator.db.filters import generic_filter_from_clauses
from orchestrator.db.filters.search_filters import (
    default_inferred_column_clauses,
    filter_exact,
    inferred_filter,
    node_to_str_val,
)
from orchestrator.utils.search_query import Node, WhereCondGenerator

logger = structlog.get_logger(__name__)


def make_product_clause(filter_generator: WhereCondGenerator) -> WhereCondGenerator:
    """The passed filter_generator takes a Node and returns a where clause acting on a ProductTable column."""

    def product_clause(node: Node) -> BinaryExpression:
        process_subscriptions = (
            select(ProcessSubscriptionTable.process_id)
            .join(SubscriptionTable)
            .join(ProductTable)
            .where(filter_generator(node))
            .subquery()
        )
        return ProcessTable.process_id.in_(process_subscriptions)

    return product_clause


def customer_clause(node: Node) -> BinaryExpression[bool] | ColumnElement[bool]:
    value = node_to_str_val(node)
    try:
        customer_uuid = UUID(value)
    except (ValueError, AttributeError):
        # Not a valid uuid, skip matching with customer_id
        return false()

    process_subscriptions = (
        select(ProcessSubscriptionTable.process_id)
        .join(SubscriptionTable)
        .where(SubscriptionTable.customer_id == customer_uuid)
        .subquery()
    )
    return ProcessTable.process_id.in_(process_subscriptions)


def make_subscription_id_clause(filter_generator: WhereCondGenerator) -> WhereCondGenerator:
    def subscription_id_clause(node: Node) -> BinaryExpression:

        process_subscriptions = (
            select(ProcessSubscriptionTable.process_id).join(SubscriptionTable).where(filter_generator(node)).subquery()
        )

        return ProcessTable.process_id.in_(process_subscriptions)

    return subscription_id_clause


def workflow_name_clause(node: Node) -> BinaryExpression:
    value = node_to_str_val(node)
    process_workflow = (
        select(ProcessTable.process_id)
        .join(WorkflowTable)
        .where(WorkflowTable.deleted_at.is_(None), WorkflowTable.name == value)
        .subquery()
    )

    return ProcessTable.process_id.in_(process_workflow)


def workflow_targets_clause(node: Node) -> BinaryExpression:
    process_workflows = (
        select(ProcessTable.process_id)
        .join(WorkflowTable)
        .where(WorkflowTable.deleted_at.is_(None), WorkflowTable.target == node_to_str_val(node))
        .subquery()
    )
    return ProcessTable.process_id.in_(process_workflows)


PROCESS_TABLE_COLUMN_CLAUSES = default_inferred_column_clauses(ProcessTable) | {
    "customer": customer_clause,
    "product": make_product_clause(inferred_filter(ProductTable.name)),
    "product_description": make_product_clause(inferred_filter(ProductTable.description)),
    "subscription_id": make_subscription_id_clause(inferred_filter(SubscriptionTable.subscription_id)),
    "tag": make_product_clause(filter_exact(ProductTable.tag)),
    "target": workflow_targets_clause,
    "workflow_name": workflow_name_clause,
}


process_filter_fields = list(PROCESS_TABLE_COLUMN_CLAUSES.keys())
filter_processes = generic_filter_from_clauses(PROCESS_TABLE_COLUMN_CLAUSES)
