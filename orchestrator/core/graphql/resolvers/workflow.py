# Copyright 2019-2026 SURF, GÉANT.
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

from collections.abc import Iterator, Sequence
from uuid import UUID

import structlog
from sqlalchemy import CompoundSelect, Select, func, select
from sqlalchemy.orm.strategy_options import _AbstractLoad

from orchestrator.core.db import db
from orchestrator.core.db.filters import Filter
from orchestrator.core.db.filters.workflow import (
    WORKFLOW_TABLE_COLUMN_CLAUSES,
    filter_workflows,
    workflow_filter_fields,
)
from orchestrator.core.db.models import WorkflowTable
from orchestrator.core.db.range.range import apply_range_to_statement
from orchestrator.core.db.sorting import Sort
from orchestrator.core.db.sorting.workflow import sort_workflows, workflow_sort_fields
from orchestrator.core.graphql.pagination import Connection
from orchestrator.core.graphql.resolvers.helpers import make_async, rows_from_statement
from orchestrator.core.graphql.resource_search import search_resource
from orchestrator.core.graphql.schemas.workflow import Workflow
from orchestrator.core.graphql.search_inputs import (
    After,
    DeprecatedFilterBy,
    DeprecatedQuery,
    DeprecatedSortBy,
    First,
    ResourceSearchInput,
)
from orchestrator.core.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.core.graphql.utils import create_resolver_error_handler, is_querying_page_data, to_graphql_result_page
from orchestrator.core.graphql.utils.get_query_loaders import get_query_loaders_for_gql_fields
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.utils.search_query import create_sqlalchemy_select

logger = structlog.get_logger(__name__)


def _graphql_workflows(stmt: Select | CompoundSelect, loaders: Sequence[_AbstractLoad]) -> Iterator[Workflow]:
    for workflow in rows_from_statement(stmt, WorkflowTable, unique=True, loaders=loaders):
        yield Workflow.from_pydantic(workflow)


@make_async
def query_workflows(
    info: OrchestratorInfo,
    filter_by: list[GraphqlFilter] | None = None,
    sort_by: list[GraphqlSort] | None = None,
    first: int = 10,
    after: int = 0,
    query: str | None = None,
) -> Connection[Workflow]:
    """List workflows with the legacy filterBy/sortBy/query arguments and offset paging."""
    _error_handler = create_resolver_error_handler(info)

    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    logger.debug("resolve_workflows() called", range=[after, after + first], sort=sort_by, filter=pydantic_filter_by)

    query_loaders = get_query_loaders_for_gql_fields(WorkflowTable, info)
    select_stmt = WorkflowTable.select().options(*query_loaders)
    select_stmt = filter_workflows(select_stmt, pydantic_filter_by, _error_handler)

    if query is not None:
        stmt = create_sqlalchemy_select(
            select_stmt,
            query,
            mappings=WORKFLOW_TABLE_COLUMN_CLAUSES,
            base_table=WorkflowTable,
            join_key=WorkflowTable.workflow_id,
        )
    else:
        stmt = select_stmt

    stmt = sort_workflows(stmt, pydantic_sort_by, _error_handler)
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery()))

    stmt = apply_range_to_statement(stmt, after, after + first + 1)

    graphql_workflows = list(_graphql_workflows(stmt, query_loaders)) if is_querying_page_data(info) else []
    return to_graphql_result_page(
        graphql_workflows, first, after, total, workflow_sort_fields(), workflow_filter_fields()
    )


@make_async
def _load_workflows(info: OrchestratorInfo, ids: Sequence[UUID]) -> dict[str, Workflow]:
    query_loaders = get_query_loaders_for_gql_fields(WorkflowTable, info)
    stmt = WorkflowTable.select().where(WorkflowTable.workflow_id.in_(ids))
    return {str(workflow.workflow_id): workflow for workflow in _graphql_workflows(stmt, query_loaders)}  # type: ignore[attr-defined]


async def search_workflows(
    info: OrchestratorInfo, search: ResourceSearchInput, first: int, after: int
) -> Connection[Workflow]:
    return await search_resource(info, EntityType.WORKFLOW, search, _load_workflows, first=first, after=after)


async def resolve_workflows(
    info: OrchestratorInfo,
    filter_by: DeprecatedFilterBy = None,
    sort_by: DeprecatedSortBy = None,
    first: First = 10,
    after: After = 0,
    query: DeprecatedQuery = None,
    search: ResourceSearchInput | None = None,
) -> Connection[Workflow]:
    if search is not None:
        return await search_workflows(info, search, first, after)
    return await query_workflows(info, filter_by, sort_by, first, after, query)
