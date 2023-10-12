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

from http import HTTPStatus
from typing import Callable
from uuid import UUID

import structlog
from sqlalchemy.inspection import inspect

from orchestrator.api.error_handling import raise_status
from orchestrator.db import ProcessSubscriptionTable, ProcessTable, ProductTable, SubscriptionTable, db
from orchestrator.db.filters.filters import QueryType, generic_filter
from orchestrator.db.filters.generic_filters import (
    generic_bool_filter,
    generic_is_like_filter,
    generic_values_in_column_filter,
)
from orchestrator.utils.helpers import to_camel

logger = structlog.get_logger(__name__)


def product_filter(query: QueryType, value: str) -> QueryType:
    process_subscriptions = (
        db.session.query(ProcessSubscriptionTable)
        .join(SubscriptionTable)
        .join(ProductTable)
        .filter(ProductTable.name.ilike("%" + value + "%"))
        .subquery()
    )
    return query.filter(ProcessTable.process_id == process_subscriptions.c.pid)


def tag_filter(query: QueryType, value: str) -> QueryType:
    tags = value.split("-")
    process_subscriptions = (
        db.session.query(ProcessSubscriptionTable)
        .join(SubscriptionTable)
        .join(ProductTable)
        .filter(ProductTable.tag.in_(tags))
        .subquery()
    )
    return query.filter(ProcessTable.process_id == process_subscriptions.c.pid)


def subscriptions_filter(query: QueryType, value: str) -> QueryType:
    process_subscriptions = (
        db.session.query(ProcessSubscriptionTable)
        .join(SubscriptionTable)
        .filter(SubscriptionTable.description.ilike("%" + value + "%"))
        .subquery()
    )
    return query.filter(ProcessTable.process_id == process_subscriptions.c.pid)


def subscription_id_filter(query: QueryType, value: str) -> QueryType:
    process_subscriptions = db.session.query(ProcessSubscriptionTable).join(SubscriptionTable)
    process_subscriptions = generic_is_like_filter(SubscriptionTable.subscription_id)(process_subscriptions, value)
    process_subscriptions = process_subscriptions.subquery()
    return query.filter(ProcessTable.process_id == process_subscriptions.c.pid)


def target_filter(query: QueryType, value: str) -> QueryType:
    targets = value.split("-")
    process_subscriptions = (
        db.session.query(ProcessSubscriptionTable)
        .filter(ProcessSubscriptionTable.workflow_target.in_(targets))
        .subquery()
    )
    return query.filter(ProcessTable.process_id == process_subscriptions.c.pid)


def organisation_filter(query: QueryType, value: str) -> QueryType:
    try:
        value_as_uuid = UUID(value)
    except (ValueError, AttributeError):
        msg = f"Not a valid organisation, must be a UUID: '{value}'"
        logger.debug(msg)
        raise_status(HTTPStatus.BAD_REQUEST, msg)

    process_subscriptions = (
        db.session.query(ProcessSubscriptionTable)
        .join(SubscriptionTable)
        .filter(SubscriptionTable.customer_id == value_as_uuid)
        .subquery()
    )
    return query.filter(ProcessTable.process_id == process_subscriptions.c.pid)


BASE_CAMEL = {to_camel(key): generic_is_like_filter(value) for key, value in inspect(ProcessTable).columns.items()}
BASE_SNAKE = {key: generic_is_like_filter(value) for key, value in inspect(ProcessTable).columns.items()}

PROCESS_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[QueryType, str], QueryType]] = (
    BASE_CAMEL
    | BASE_SNAKE
    | {
        "isTask": generic_bool_filter(ProcessTable.is_task),
        "is_task": generic_bool_filter(ProcessTable.is_task),
        "assignee": generic_values_in_column_filter(ProcessTable.assignee),
        "lastStatus": generic_values_in_column_filter(ProcessTable.last_status),
        "product": product_filter,
        "productTag": tag_filter,
        "subscriptions": subscriptions_filter,
        "subscriptionId": subscription_id_filter,
        "subscription_id": subscription_id_filter,
        "target": target_filter,
        "organisation": organisation_filter,
        "istask": generic_bool_filter(ProcessTable.is_task),  # TODO: will be removed in 1.4
        "status": generic_values_in_column_filter(ProcessTable.last_status),  # TODO: will be removed in 1.4
        "last_status": generic_values_in_column_filter(ProcessTable.last_status),  # TODO: will be removed in 1.4
        "tag": tag_filter,  # TODO: will be removed in 1.4
        "creator": generic_is_like_filter(ProcessTable.created_by),  # TODO: will be removed in 1.4
    }
)

process_filter_fields = list(PROCESS_FILTER_FUNCTIONS_BY_COLUMN.keys())
filter_processes = generic_filter(PROCESS_FILTER_FUNCTIONS_BY_COLUMN)
