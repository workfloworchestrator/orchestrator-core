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

import structlog
from sqlalchemy import func, select

from orchestrator.core.db import db
from orchestrator.core.db.filters import Filter
from orchestrator.core.db.filters.product import PRODUCT_TABLE_COLUMN_CLAUSES, filter_products, product_filter_fields
from orchestrator.core.db.models import ProductTable
from orchestrator.core.db.range.range import apply_range_to_statement
from orchestrator.core.db.sorting import Sort
from orchestrator.core.db.sorting.product import product_sort_fields, sort_products
from orchestrator.core.graphql.pagination import Connection
from orchestrator.core.graphql.resolvers.helpers import make_async, rows_from_statement
from orchestrator.core.graphql.schemas.product import ProductType
from orchestrator.core.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.core.graphql.utils import create_resolver_error_handler, is_querying_page_data, to_graphql_result_page
from orchestrator.core.graphql.utils.get_query_loaders import get_query_loaders_for_gql_fields
from orchestrator.core.utils.search_query import create_sqlalchemy_select

logger = structlog.get_logger(__name__)


@make_async
def resolve_products(
    info: OrchestratorInfo,
    filter_by: list[GraphqlFilter] | None = None,
    sort_by: list[GraphqlSort] | None = None,
    first: int = 10,
    after: int = 0,
    query: str | None = None,
) -> Connection[ProductType]:
    _error_handler = create_resolver_error_handler(info)

    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    logger.debug("resolve_products() called", range=[after, after + first], sort=sort_by, filter=pydantic_filter_by)

    query_loaders = get_query_loaders_for_gql_fields(ProductTable, info)
    select_stmt = select(ProductTable).options(*query_loaders)
    select_stmt = filter_products(select_stmt, pydantic_filter_by, _error_handler)

    if query is not None:
        stmt = create_sqlalchemy_select(
            select_stmt,
            query,
            mappings=PRODUCT_TABLE_COLUMN_CLAUSES,
            base_table=ProductTable,
            join_key=ProductTable.product_id,
        )
    else:
        stmt = select_stmt

    stmt = sort_products(stmt, pydantic_sort_by, _error_handler)
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = apply_range_to_statement(stmt, after, after + first + 1)

    graphql_products = []
    if is_querying_page_data(info):
        products = rows_from_statement(stmt, ProductTable, unique=True, loaders=query_loaders)
        graphql_products = [ProductType.from_pydantic(p) for p in products]
    return to_graphql_result_page(graphql_products, first, after, total, product_sort_fields(), product_filter_fields())
