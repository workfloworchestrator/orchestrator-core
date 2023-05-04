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

from http import HTTPStatus
from typing import Callable
from uuid import UUID

import structlog
from sqlalchemy import String, cast

from orchestrator.api.error_handling import raise_status
from orchestrator.db import ProcessSubscriptionTable, ProcessTable, ProductTable, SubscriptionTable, db
from orchestrator.db.database import SearchQuery
from orchestrator.db.filters.filters import generic_filter

logger = structlog.get_logger(__name__)


def pid_filter(query: SearchQuery, value: str) -> SearchQuery:
    return query.filter(cast(ProcessTable.pid, String).ilike("%" + value + "%"))


def is_task_filter(query: SearchQuery, value: str) -> SearchQuery:
    value_as_bool = value.lower() in ("yes", "y", "ye", "true", "1", "ja")
    return query.filter(ProcessTable.is_task.is_(value_as_bool))


def assignee_filter(query: SearchQuery, value: str) -> SearchQuery:
    assignees = value.split("-")
    return query.filter(ProcessTable.assignee.in_(assignees))


def status_filter(query: SearchQuery, value: str) -> SearchQuery:
    statuses = value.split("-")
    return query.filter(ProcessTable.last_status.in_(statuses))


def workflow_filter(query: SearchQuery, value: str) -> SearchQuery:
    return query.filter(ProcessTable.workflow.ilike("%" + value + "%"))


def creator_filter(query: SearchQuery, value: str) -> SearchQuery:
    return query.filter(ProcessTable.created_by.ilike("%" + value + "%"))


def organisation_filter(query: SearchQuery, value: str) -> SearchQuery:
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
    return query.filter(ProcessTable.pid == process_subscriptions.c.pid)


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


def target_filter(query: SearchQuery, value: str) -> SearchQuery:
    targets = value.split("-")
    process_subscriptions = (
        db.session.query(ProcessSubscriptionTable)
        .filter(ProcessSubscriptionTable.workflow_target.in_(targets))
        .subquery()
    )
    return query.filter(ProcessTable.pid == process_subscriptions.c.pid)


VALID_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[SearchQuery, str], SearchQuery]] = {
    "pid": pid_filter,
    "istask": is_task_filter,
    "assignee": assignee_filter,
    "status": status_filter,
    "workflow": workflow_filter,
    "creator": creator_filter,
    "organisation": organisation_filter,
    "product": product_filter,
    "tag": tag_filter,
    "subscription": subscriptions_filter,
    "target": target_filter,
}


filter_processes = generic_filter(VALID_FILTER_FUNCTIONS_BY_COLUMN)
