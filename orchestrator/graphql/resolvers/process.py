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
from sqlalchemy.orm import defer, joinedload

from orchestrator.db import ProcessSubscriptionTable, ProcessTable, SubscriptionTable
from orchestrator.db.filters import Filter
from orchestrator.db.filters.process import filter_processes
from orchestrator.db.range import apply_range_to_query
from orchestrator.db.sorting import Sort
from orchestrator.db.sorting.process import sort_processes
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.schemas.process import ProcessGraphqlSchema, ProcessType
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils.create_resolver_error_handler import create_resolver_error_handler
from orchestrator.graphql.utils.to_graphql_result_page import to_graphql_result_page
from orchestrator.services.processes import load_process
from orchestrator.utils.show_process import show_process

logger = structlog.get_logger(__name__)


def enrich_process(process: ProcessTable) -> ProcessGraphqlSchema:
    p = load_process(process)
    data = show_process(process, p)
    return ProcessGraphqlSchema(**data)


async def resolve_processes(
    info: OrchestratorInfo,
    filter_by: Union[list[GraphqlFilter], None] = None,
    sort_by: Union[list[GraphqlSort], None] = None,
    first: int = 10,
    after: int = 0,
) -> Connection[ProcessType]:
    _error_handler = create_resolver_error_handler(info)
    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    logger.debug("resolve_processes() called", range=[after, after + first], sort=sort_by, filter=pydantic_filter_by)

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
    graphql_processes = [ProcessType.from_pydantic(enrich_process(p)) for p in processes]
    return to_graphql_result_page(graphql_processes, first, after, total)
