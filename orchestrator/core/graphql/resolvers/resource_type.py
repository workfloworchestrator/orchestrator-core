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
from orchestrator.core.db.filters.resource_type import (
    RESOURCE_TYPE_TABLE_COLUMN_CLAUSES,
    filter_resource_types,
    resource_type_filter_fields,
)
from orchestrator.core.db.models import ResourceTypeTable
from orchestrator.core.db.range import apply_range_to_statement
from orchestrator.core.db.sorting import Sort
from orchestrator.core.db.sorting.resource_type import resource_type_sort_fields, sort_resource_types
from orchestrator.core.graphql.pagination import Connection
from orchestrator.core.graphql.resolvers.helpers import make_async, rows_from_statement
from orchestrator.core.graphql.resource_search import search_resource
from orchestrator.core.graphql.schemas.resource_type import ResourceType
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


def _graphql_resource_types(stmt: Select | CompoundSelect, loaders: Sequence[_AbstractLoad]) -> Iterator[ResourceType]:
    for resource_type in rows_from_statement(stmt, ResourceTypeTable, loaders=loaders):
        yield ResourceType.from_pydantic(resource_type)


@make_async
def query_resource_types(
    info: OrchestratorInfo,
    filter_by: list[GraphqlFilter] | None = None,
    sort_by: list[GraphqlSort] | None = None,
    first: int = 10,
    after: int = 0,
    query: str | None = None,
) -> Connection[ResourceType]:
    """List resource types with the legacy filterBy/sortBy/query arguments and offset paging."""
    _error_handler = create_resolver_error_handler(info)

    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    logger.debug(
        "resolve_resource_types() called", range=[after, after + first], sort=sort_by, filter=pydantic_filter_by
    )
    query_loaders = get_query_loaders_for_gql_fields(ResourceTypeTable, info)
    select_stmt = select(ResourceTypeTable).options(*query_loaders)
    select_stmt = filter_resource_types(select_stmt, pydantic_filter_by, _error_handler)

    if query is not None:
        stmt = create_sqlalchemy_select(
            select_stmt,
            query,
            mappings=RESOURCE_TYPE_TABLE_COLUMN_CLAUSES,
            base_table=ResourceTypeTable,
            join_key=ResourceTypeTable.resource_type_id,
        )
    else:
        stmt = select_stmt

    stmt = sort_resource_types(stmt, pydantic_sort_by, _error_handler)
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = apply_range_to_statement(stmt, after, after + first + 1)

    graphql_resource_types = list(_graphql_resource_types(stmt, query_loaders)) if is_querying_page_data(info) else []
    return to_graphql_result_page(
        graphql_resource_types, first, after, total, resource_type_sort_fields(), resource_type_filter_fields()
    )


@make_async
def _load_resource_types(info: OrchestratorInfo, ids: Sequence[UUID]) -> dict[str, ResourceType]:
    query_loaders = get_query_loaders_for_gql_fields(ResourceTypeTable, info)
    stmt = select(ResourceTypeTable).where(ResourceTypeTable.resource_type_id.in_(ids))
    return {
        str(resource_type.resource_type_id): resource_type  # type: ignore[attr-defined]
        for resource_type in _graphql_resource_types(stmt, query_loaders)
    }


# Todo: move into resolve_resource_types once the deprecated query_resource_types is removed, see #2074
async def _search_resource_types(
    info: OrchestratorInfo, search: ResourceSearchInput, first: int, after: int
) -> Connection[ResourceType]:
    return await search_resource(info, EntityType.RESOURCE_TYPE, search, _load_resource_types, first=first, after=after)


async def resolve_resource_types(
    info: OrchestratorInfo,
    filter_by: DeprecatedFilterBy = None,
    sort_by: DeprecatedSortBy = None,
    first: First = 10,
    after: After = 0,
    query: DeprecatedQuery = None,
    search: ResourceSearchInput | None = None,
) -> Connection[ResourceType]:
    if search is not None:
        return await _search_resource_types(info, search, first, after)
    return await query_resource_types(info, filter_by, sort_by, first, after, query)
