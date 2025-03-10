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
from uuid import UUID

import structlog
from pydantic.alias_generators import to_camel as to_lower_camel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from orchestrator.db import ProcessTable, db
from orchestrator.db.filters import Filter
from orchestrator.db.filters.process import PROCESS_TABLE_COLUMN_CLAUSES, filter_processes, process_filter_fields
from orchestrator.db.models import ProcessSubscriptionTable, SubscriptionTable
from orchestrator.db.range import apply_range_to_statement
from orchestrator.db.sorting import Sort
from orchestrator.db.sorting.process import process_sort_fields, sort_processes
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.resolvers.helpers import rows_from_statement
from orchestrator.graphql.schemas.process import ProcessType
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils import (
    create_resolver_error_handler,
    is_query_detailed,
    is_querying_page_data,
    to_graphql_result_page,
)
from orchestrator.graphql.utils.get_query_loaders import get_query_loaders_for_gql_fields
from orchestrator.schemas.process import ProcessSchema
from orchestrator.services.processes import load_process
from orchestrator.utils.enrich_process import enrich_process
from orchestrator.utils.search_query import create_sqlalchemy_select

logger = structlog.get_logger(__name__)


detailed_props = ("steps", "form", "current_state")
simple_props = tuple([to_lower_camel(key) for key in ProcessType.__annotations__ if key not in detailed_props])

_is_process_detailed = is_query_detailed(simple_props)


def _enrich_process(process: ProcessTable, with_details: bool = False) -> ProcessSchema:
    pstat = load_process(process) if with_details else None
    process_data = enrich_process(process, pstat)
    return ProcessSchema(**process_data)


async def resolve_process(info: OrchestratorInfo, process_id: UUID) -> ProcessType | None:
    query_loaders = get_query_loaders_for_gql_fields(ProcessTable, info)
    stmt = select(ProcessTable).options(*query_loaders).where(ProcessTable.process_id == process_id)
    if process := db.session.scalar(stmt):
        is_detailed = _is_process_detailed(info)
        return ProcessType.from_pydantic(_enrich_process(process, is_detailed))
    return None


async def resolve_processes(
    info: OrchestratorInfo,
    filter_by: list[GraphqlFilter] | None = None,
    sort_by: list[GraphqlSort] | None = None,
    first: int = 10,
    after: int = 0,
    query: str | None = None,
) -> Connection[ProcessType]:
    _error_handler = create_resolver_error_handler(info)
    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    logger.debug("resolve_processes() called", range=[after, after + first], sort=sort_by, filter=pydantic_filter_by)

    # Hardcoded loaders required for _enrich_process
    default_loaders = [
        selectinload(ProcessTable.process_subscriptions)
        .selectinload(ProcessSubscriptionTable.subscription)
        .joinedload(SubscriptionTable.product)
    ]
    query_loaders = get_query_loaders_for_gql_fields(ProcessTable, info) or default_loaders
    select_stmt = select(ProcessTable).options(*query_loaders)
    select_stmt = filter_processes(select_stmt, pydantic_filter_by, _error_handler)
    if query is not None:
        stmt = create_sqlalchemy_select(
            select_stmt,
            query,
            mappings=PROCESS_TABLE_COLUMN_CLAUSES,
            base_table=ProcessTable,
            join_key=ProcessTable.process_id,
        )
    else:
        stmt = select_stmt

    stmt = sort_processes(stmt, pydantic_sort_by, _error_handler)
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = apply_range_to_statement(stmt, after, after + first + 1)

    graphql_processes = []
    if is_querying_page_data(info):
        processes = rows_from_statement(stmt, ProcessTable, loaders=query_loaders)
        is_detailed = _is_process_detailed(info)
        graphql_processes = [ProcessType.from_pydantic(_enrich_process(process, is_detailed)) for process in processes]
    return to_graphql_result_page(
        graphql_processes, first, after, total, process_sort_fields(), process_filter_fields()
    )
