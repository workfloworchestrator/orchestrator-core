import structlog
from sqlalchemy import func, select

from orchestrator.db import db
from orchestrator.db.filters import Filter
from orchestrator.db.filters.product_block import (
    PRODUCT_BLOCK_TABLE_COLUMN_CLAUSES,
    filter_product_blocks,
    product_block_filter_fields,
)
from orchestrator.db.models import ProductBlockTable
from orchestrator.db.range.range import apply_range_to_statement
from orchestrator.db.sorting import Sort
from orchestrator.db.sorting.product_block import product_block_sort_fields, sort_product_blocks
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.resolvers.helpers import rows_from_statement
from orchestrator.graphql.schemas.product_block import ProductBlock
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils import create_resolver_error_handler, is_querying_page_data, to_graphql_result_page
from orchestrator.utils.search_query import create_sqlalchemy_select

logger = structlog.get_logger(__name__)


async def resolve_product_blocks(
    info: OrchestratorInfo,
    filter_by: list[GraphqlFilter] | None = None,
    sort_by: list[GraphqlSort] | None = None,
    first: int = 10,
    after: int = 0,
    query: str | None = None,
) -> Connection[ProductBlock]:
    _error_handler = create_resolver_error_handler(info)

    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    logger.debug(
        "resolve_product_blocks() called", range=[after, after + first], sort=sort_by, filter=pydantic_filter_by
    )

    select_stmt = select(ProductBlockTable)
    select_stmt = filter_product_blocks(select_stmt, pydantic_filter_by, _error_handler)

    if query is not None:
        stmt = create_sqlalchemy_select(
            select_stmt,
            query,
            mappings=PRODUCT_BLOCK_TABLE_COLUMN_CLAUSES,
            base_table=ProductBlockTable,
            join_key=ProductBlockTable.product_block_id,
        )
    else:
        stmt = select_stmt

    stmt = sort_product_blocks(stmt, pydantic_sort_by, _error_handler)
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = apply_range_to_statement(stmt, after, after + first + 1)

    graphql_product_blocks = []
    if is_querying_page_data(info):
        product_blocks = rows_from_statement(stmt, ProductBlockTable)
        graphql_product_blocks = [ProductBlock.from_pydantic(p) for p in product_blocks]
    return to_graphql_result_page(
        graphql_product_blocks, first, after, total, product_block_sort_fields(), product_block_filter_fields()
    )
