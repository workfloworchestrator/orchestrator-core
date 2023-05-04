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

from typing import Union

import structlog
from graphql import GraphQLError
from sqlalchemy.orm import defer, joinedload

from orchestrator.db import ProcessSubscriptionTable, ProcessTable, SubscriptionTable
from orchestrator.db.filters import CallableErrorHander, Filter
from orchestrator.db.filters.process import filter_processes
from orchestrator.db.range import apply_range_to_query
from orchestrator.db.sorting import Sort
from orchestrator.db.sorting.process import sort_processes
from orchestrator.graphql.pagination import Connection, PageInfo
from orchestrator.graphql.schemas.process import ProcessGraphqlSchema, ProcessType
from orchestrator.graphql.types import CustomInfo, GraphqlFilter, GraphqlSort
from orchestrator.services.processes import load_process
from orchestrator.utils.show_process import show_process

logger = structlog.get_logger(__name__)


def enrich_process(process: ProcessTable) -> ProcessGraphqlSchema:
    p = load_process(process)
    data = show_process(process, p)
    return ProcessGraphqlSchema(**data)


def handle_process_error(info: CustomInfo) -> CallableErrorHander:
    def _handle_process_error(message: str, **kwargs) -> None:  # type: ignore
        logger.debug(message, **kwargs)
        extra_values = dict(kwargs.items()) if kwargs else {}
        info.context.errors.append(GraphQLError(message=message, path=info.path, extensions=extra_values))

    return _handle_process_error


async def resolve_processes(
    info: CustomInfo,
    filter_by: Union[list[GraphqlFilter], None] = None,
    sort_by: Union[list[GraphqlSort], None] = None,
    first: int = 10,
    after: int = 0,
) -> Connection[ProcessType]:
    _error_handler = handle_process_error(info)

    _range: Union[list[int], None] = [after, after + first] if after is not None and first else None
    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
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
    query = sort_processes(query, pydantic_sort_by, _error_handler)
    total = query.count()
    query = apply_range_to_query(query, after, first)

    processes = query.all()
    has_next_page = len(processes) > first

    # exclude last item as it was fetched to know if there is a next page
    processes = processes[:first]
    processes_length = len(processes)
    start_cursor = after if processes_length else None
    end_cursor = after + processes_length - 1
    page_processes = [ProcessType.from_pydantic(enrich_process(p)) for p in processes]

    return Connection(
        page=page_processes,
        page_info=PageInfo(
            has_previous_page=bool(after),
            has_next_page=has_next_page,
            start_cursor=start_cursor,
            end_cursor=end_cursor,
            total_items=total if total else None,
        ),
    )
