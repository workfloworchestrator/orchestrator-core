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

from typing import Callable

import structlog

from orchestrator.db import ProcessSubscriptionTable, ProcessTable, ProductTable, SubscriptionTable, db
from orchestrator.db.database import SearchQuery
from orchestrator.db.filters.filters import generic_filter
from orchestrator.db.filters.generic_filters import (
    generic_bool_filter,
    generic_is_like_filter,
    generic_values_in_column_filter,
)

logger = structlog.get_logger(__name__)


def product_filter(query: SearchQuery, value: str) -> SearchQuery:
    process_subscriptions = (
        db.session.query(ProcessSubscriptionTable)
        .join(SubscriptionTable, ProductTable)
        .filter(ProductTable.name.ilike("%" + value + "%"))
        .subquery()
    )
    return query.filter(ProcessTable.pid == process_subscriptions.c.pid)


def tag_filter(query: SearchQuery, value: str) -> SearchQuery:
    tags = value.split("-")
    process_subscriptions = (
        db.session.query(ProcessSubscriptionTable)
        .join(SubscriptionTable, ProductTable)
        .filter(ProductTable.tag.in_(tags))
        .subquery()
    )
    return query.filter(ProcessTable.pid == process_subscriptions.c.pid)


def subscriptions_filter(query: SearchQuery, value: str) -> SearchQuery:
    process_subscriptions = (
        db.session.query(ProcessSubscriptionTable)
        .join(SubscriptionTable)
        .filter(SubscriptionTable.description.ilike("%" + value + "%"))
        .subquery()
    )
    return query.filter(ProcessTable.pid == process_subscriptions.c.pid)


def subscription_id_filter(query: SearchQuery, value: str) -> SearchQuery:
    process_subscriptions = db.session.query(ProcessSubscriptionTable).join(SubscriptionTable)
    process_subscriptions = generic_is_like_filter(SubscriptionTable.subscription_id)(process_subscriptions, value)
    process_subscriptions = process_subscriptions.subquery()
    return query.filter(ProcessTable.pid == process_subscriptions.c.pid)


def target_filter(query: SearchQuery, value: str) -> SearchQuery:
    targets = value.split("-")
    process_subscriptions = (
        db.session.query(ProcessSubscriptionTable)
        .filter(ProcessSubscriptionTable.workflow_target.in_(targets))
        .subquery()
    )
    return query.filter(ProcessTable.pid == process_subscriptions.c.pid)


PROCESS_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[SearchQuery, str], SearchQuery]] = {
    "pid": generic_is_like_filter(ProcessTable.pid),
    "istask": generic_bool_filter(ProcessTable.is_task),
    "assignee": generic_values_in_column_filter(ProcessTable.assignee),
    "status": generic_values_in_column_filter(ProcessTable.last_status),
    "workflow": generic_is_like_filter(ProcessTable.workflow),
    "creator": generic_is_like_filter(ProcessTable.created_by),
    "product": product_filter,
    "tag": tag_filter,
    "subscription": subscriptions_filter,
    "subscriptionId": subscription_id_filter,
    "target": target_filter,
}


filter_processes = generic_filter(PROCESS_FILTER_FUNCTIONS_BY_COLUMN)
