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

"""Module that implements process related API endpoints."""

from enum import Enum
from http import HTTPStatus
from uuid import UUID

import strawberry
import structlog
from more_itertools import chunked, flatten, one
from sqlalchemy import String, cast
from sqlalchemy.orm import defer, joinedload
from sqlalchemy.sql import expression
from strawberry.types.nodes import SelectedField, Selection

from orchestrator.api.error_handling import raise_status
from orchestrator.api.helpers import VALID_SORT_KEYS
from orchestrator.db import ProcessSubscriptionTable, ProcessTable, ProductTable, SubscriptionTable, db
from orchestrator.db.database import SearchQuery
from orchestrator.graphql.pagination import Connection, PageInfo
from orchestrator.graphql.schemas.process import ProcessType
from orchestrator.schemas import ProcessSchema
from orchestrator.schemas.process import ProcessStepSchema

logger = structlog.get_logger(__name__)


def get_selections(selected_field: Selection) -> list[Selection]:
    def has_field_name(selection: Selection, field_name: str) -> bool:
        return isinstance(selection, SelectedField) and selection.name == field_name

    edges_field = [selection for selection in selected_field.selections if has_field_name(selection, "edges")]

    if not edges_field:
        return selected_field.selections

    node_field = [selection for selection in one(edges_field).selections if has_field_name(selection, "node")]

    return one(node_field).selections if node_field else []


def enrich_process(p: ProcessTable) -> ProcessSchema:
    # p.subscriptions is a non JSON serializable AssociationProxy
    # So we need to build a list of Subscriptions here.
    return ProcessSchema(
        assignee=p.assignee,
        created_by=p.created_by,
        failed_reason=p.failed_reason,
        last_modified=p.last_modified_at,
        id=p.pid,
        started=p.started_at.timestamp(),
        last_step=p.last_step,
        workflow_name=p.workflow,
        is_task=p.is_task,
        status=p.last_status,
        steps=[
            ProcessStepSchema(
                stepid=step.stepid,
                name=step.name,
                status=step.status,
                created_by=step.created_by,
                executed=step.executed_at,
                commit_hash=step.commit_hash,
                state=step.state,
            )
            for step in p.steps
        ],
        current_state={},
        subscriptions=[],
    )


@strawberry.enum(description="Sort order (ASC or DESC)")
class SortOrder(Enum):
    ASC = "asc"
    DESC = "desc"


@strawberry.input(description="Sort processes by attribute")
class ProcessSort:
    field: str = strawberry.field(description="Field to sort on")
    order: SortOrder = strawberry.field(default=SortOrder.ASC, description="Sort order (ASC or DESC")


def filter_processes(query: SearchQuery, filter: list[str] | None = None) -> SearchQuery:
    if filter is not None:
        if len(filter) == 0 or (len(filter) % 2) > 0:
            raise_status(HTTPStatus.BAD_REQUEST, "Invalid number of filter arguments")

        for filter_pair in chunked(filter, 2):
            field, value = filter_pair
            field = field.lower()
            if value is not None:
                if field == "istask":
                    value_as_bool = value.lower() in ("yes", "y", "ye", "true", "1", "ja")
                    query = query.filter(ProcessTable.is_task.is_(value_as_bool))
                elif field == "assignee":
                    assignees = value.split("-")
                    query = query.filter(ProcessTable.assignee.in_(assignees))
                elif field == "status":
                    statuses = value.split("-")
                    query = query.filter(ProcessTable.last_status.in_(statuses))
                elif field == "workflow":
                    query = query.filter(ProcessTable.workflow.ilike("%" + value + "%"))
                elif field == "creator":
                    query = query.filter(ProcessTable.created_by.ilike("%" + value + "%"))
                elif field == "organisation":
                    try:
                        value_as_uuid = UUID(value)
                    except (ValueError, AttributeError):
                        msg = "Not a valid customer_id, must be a UUID: '{value}'"
                        logger.exception(msg)
                        raise_status(HTTPStatus.BAD_REQUEST, msg)
                    process_subscriptions = (
                        db.session.query(ProcessSubscriptionTable)
                        .join(SubscriptionTable)
                        .filter(SubscriptionTable.customer_id == value_as_uuid)
                        .subquery()
                    )
                    query = query.filter(ProcessTable.pid == process_subscriptions.c.pid)
                elif field == "product":
                    process_subscriptions = (
                        db.session.query(ProcessSubscriptionTable)
                        .join(SubscriptionTable, ProductTable)
                        .filter(ProductTable.name.ilike("%" + value + "%"))
                        .subquery()
                    )
                    query = query.filter(ProcessTable.pid == process_subscriptions.c.pid)
                elif field == "tag":
                    tags = value.split("-")
                    process_subscriptions = (
                        db.session.query(ProcessSubscriptionTable)
                        .join(SubscriptionTable, ProductTable)
                        .filter(ProductTable.tag.in_(tags))
                        .subquery()
                    )
                    query = query.filter(ProcessTable.pid == process_subscriptions.c.pid)
                elif field == "subscriptions":
                    process_subscriptions = (
                        db.session.query(ProcessSubscriptionTable)
                        .join(SubscriptionTable)
                        .filter(SubscriptionTable.description.ilike("%" + value + "%"))
                        .subquery()
                    )
                    query = query.filter(ProcessTable.pid == process_subscriptions.c.pid)
                elif field == "pid":
                    query = query.filter(cast(ProcessTable.pid, String).ilike("%" + value + "%"))
                elif field == "target":
                    targets = value.split("-")
                    process_subscriptions = (
                        db.session.query(ProcessSubscriptionTable)
                        .filter(ProcessSubscriptionTable.workflow_target.in_(targets))
                        .subquery()
                    )
                    query = query.filter(ProcessTable.pid == process_subscriptions.c.pid)
                else:
                    raise_status(HTTPStatus.BAD_REQUEST, f"Invalid filter '{field}'")
    return query


def sort_processes(query: SearchQuery, sort_by: list[ProcessSort] | None = None) -> SearchQuery:
    if sort_by is not None:
        for item in sort_by:
            if item.field in VALID_SORT_KEYS:
                sort_key = VALID_SORT_KEYS[item.field]
                if item.order == SortOrder.DESC:
                    query = query.order_by(expression.desc(ProcessTable.__dict__[sort_key]))
                else:
                    query = query.order_by(expression.asc(ProcessTable.__dict__[sort_key]))
            else:
                raise_status(HTTPStatus.BAD_REQUEST, "Invalid Sort parameters")
    return query


def set_processes_range(query: SearchQuery, after: int, first: int) -> SearchQuery:
    if after is not None and first:
        if after >= after + first:
            msg = "range start must be lower than end"
            logger.exception(msg)
            raise_status(HTTPStatus.BAD_REQUEST, msg)
        query = query.offset(after).limit(first + 1)
    return query


async def resolve_processes(
    filter_by: list[tuple[str, str]] | None = None,
    sort_by: list[ProcessSort] | None = None,
    first: int = 10,
    after: int = 0,
) -> Connection[ProcessType]:
    _range: list[int] | None = [after, after + first] if after is not None and first else None
    _filter: list[str] | None = list(flatten(filter_by)) if filter_by else None
    logger.info("processes_filterable() called", range=_range, sort=sort_by, filter=_filter)

    # the joinedload on ProcessSubscriptionTable.subscription via ProcessBaseSchema.process_subscriptions prevents a query for every subscription later.
    # tracebacks are not presented in the list of processes and can be really large.
    query = ProcessTable.query.options(
        joinedload(ProcessTable.process_subscriptions)
        .joinedload(ProcessSubscriptionTable.subscription)
        .joinedload(SubscriptionTable.product),
        defer("traceback"),
    )

    query = filter_processes(query, _filter)
    query = sort_processes(query, sort_by)
    total = query.count()
    query = set_processes_range(query, after, first)

    processes = query.all()
    has_next_page = len(processes) > first

    # exclude last item as it was fetched to know if there is a next page
    processes = processes[:first]
    processes_length = len(processes)
    start_cursor = after if processes_length else None
    end_cursor = after + processes_length - 1

    return Connection(
        page=[ProcessType.from_pydantic(enrich_process(p)) for p in processes] if processes else [],
        page_info=PageInfo(
            has_previous_page=bool(after),
            has_next_page=has_next_page,
            start_cursor=start_cursor,
            end_cursor=end_cursor,
            total_items=total if total else None,
        ),
    )
