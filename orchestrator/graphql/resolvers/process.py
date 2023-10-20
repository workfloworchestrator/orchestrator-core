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
from pydantic.utils import to_lower_camel
from sqlalchemy import func, select
from sqlalchemy.orm import defer, selectinload

from orchestrator.db import ProcessSubscriptionTable, ProcessTable, SubscriptionTable, db
from orchestrator.db.filters import Filter
from orchestrator.db.filters.process import filter_processes, process_filter_fields
from orchestrator.db.range import apply_range_to_statement
from orchestrator.db.sorting import Sort
from orchestrator.db.sorting.process import process_sort_fields, sort_processes
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.schemas.process import ProcessType
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils.create_resolver_error_handler import create_resolver_error_handler
from orchestrator.graphql.utils.is_query_detailed import is_query_detailed
from orchestrator.graphql.utils.to_graphql_result_page import to_graphql_result_page
from orchestrator.schemas.process import ProcessSchema
from orchestrator.services.processes import load_process
from orchestrator.utils.enrich_process import enrich_process

logger = structlog.get_logger(__name__)


detailed_props = ("steps", "form", "current_state")
simple_props = tuple([to_lower_camel(key) for key in ProcessType.__annotations__ if key not in detailed_props])

_is_process_detailed = is_query_detailed(simple_props)


def _enrich_process(process: ProcessTable, with_details: bool = False) -> ProcessSchema:
    pstat = load_process(process) if with_details else None
    process_data = enrich_process(process, pstat)
    return ProcessSchema(**process_data)


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
    stmt = select(ProcessTable).options(
        selectinload(ProcessTable.process_subscriptions)
        .selectinload(ProcessSubscriptionTable.subscription)
        .selectinload(SubscriptionTable.product),
        defer(ProcessTable.traceback),
    )

    stmt = filter_processes(stmt, pydantic_filter_by, _error_handler)
    stmt = sort_processes(stmt, pydantic_sort_by, _error_handler)
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = apply_range_to_statement(stmt, after, after + first + 1)

    processes = db.session.scalars(stmt).all()

    is_detailed = _is_process_detailed(info)
    graphql_processes = [ProcessType.from_pydantic(_enrich_process(process, is_detailed)) for process in processes]
    return to_graphql_result_page(graphql_processes, first, after, total, process_sort_fields, process_filter_fields)
