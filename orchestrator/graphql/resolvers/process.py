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

import strawberry
import structlog
from graphql import GraphQLError
from sqlalchemy.orm import defer, joinedload
from sqlalchemy.sql import expression

from orchestrator.api.error_handling import raise_status
from orchestrator.api.helpers import VALID_SORT_KEYS
from orchestrator.db import ProcessSubscriptionTable, ProcessTable, SubscriptionTable
from orchestrator.db.database import SearchQuery
from orchestrator.db.filters import CallableErrorHander, Filter
from orchestrator.db.filters.process import filter_processes
from orchestrator.graphql.pagination import Connection, PageInfo
from orchestrator.graphql.schemas.process import ProcessType
from orchestrator.graphql.types import CustomInfo, GraphqlFilter
from orchestrator.schemas import ProcessSchema
from orchestrator.schemas.process import ProcessStepSchema

logger = structlog.get_logger(__name__)


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


def handle_process_error(info: CustomInfo) -> CallableErrorHander:  # type: ignore
    def _handle_process_error(message: str, **kwargs) -> None:  # type: ignore
        logger.debug(message, **kwargs)
        extra_values = {k: v for k, v in kwargs.items()} if kwargs else {}
        info.context.errors.append(GraphQLError(message=message, path=info.path, extensions=extra_values))

    return _handle_process_error


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
    info: CustomInfo,
    filter_by: list[GraphqlFilter] | None = None,
    sort_by: list[ProcessSort] | None = None,
    first: int = 10,
    after: int = 0,
) -> Connection[ProcessType]:
    _error_handler = handle_process_error(info)

    _range: list[int] | None = [after, after + first] if after is not None and first else None
    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    logger.info("resolve_processes() called", range=_range, sort=sort_by, filter=pydantic_filter_by)

    # the joinedload on ProcessSubscriptionTable.subscription via ProcessBaseSchema.process_subscriptions prevents a query for every subscription later.
    # tracebacks are not presented in the list of processes and can be really large.
    query = ProcessTable.query.options(
        joinedload(ProcessTable.process_subscriptions)
        .joinedload(ProcessSubscriptionTable.subscription)
        .joinedload(SubscriptionTable.product),
        defer("traceback"),
    )

    query = filter_processes(query, pydantic_filter_by, _error_handler)
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
