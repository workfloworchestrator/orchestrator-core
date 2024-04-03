import structlog
from sqlalchemy import func, select

from orchestrator.db import db
from orchestrator.db.filters import Filter
from orchestrator.db.filters.product import PRODUCT_TABLE_COLUMN_CLAUSES, filter_products, product_filter_fields
from orchestrator.db.models import ProductTable
from orchestrator.db.range.range import apply_range_to_statement
from orchestrator.db.sorting import Sort
from orchestrator.db.sorting.product import product_sort_fields, sort_products
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.resolvers.helpers import rows_from_statement
from orchestrator.graphql.schemas.product import ProductType
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils import create_resolver_error_handler, is_querying_page_data, to_graphql_result_page
from orchestrator.utils.search_query import create_sqlalchemy_select

logger = structlog.get_logger(__name__)


async def resolve_products(
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

    select_stmt = select(ProductTable)
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
        products = rows_from_statement(stmt, ProductTable, unique=True)
        graphql_products = [ProductType.from_pydantic(p) for p in products]
    return to_graphql_result_page(graphql_products, first, after, total, product_sort_fields(), product_filter_fields())
