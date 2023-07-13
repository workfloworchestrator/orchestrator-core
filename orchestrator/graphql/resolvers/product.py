from typing import Union

import structlog

from orchestrator.db.filters import Filter
from orchestrator.db.filters.product import filter_products
from orchestrator.db.models import ProductTable
from orchestrator.db.range.range import apply_range_to_query
from orchestrator.db.sorting.product import sort_products
from orchestrator.db.sorting.sorting import Sort
from orchestrator.graphql.pagination import Connection, PageInfo
from orchestrator.graphql.schemas.product import ProductType
from orchestrator.graphql.types import CustomInfo, GraphqlFilter, GraphqlSort
from orchestrator.graphql.utils.create_resolver_error_handler import create_resolver_error_handler

logger = structlog.get_logger(__name__)


async def resolve_products(
    info: CustomInfo,
    filter_by: Union[list[GraphqlFilter], None] = None,
    sort_by: Union[list[GraphqlSort], None] = None,
    first: int = 10,
    after: int = 0,
) -> Connection[ProductType]:
    _error_handler = create_resolver_error_handler(info)

    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    logger.info("resolve_products() called", range=[after, after + first], sort=sort_by, filter=pydantic_filter_by)

    query = filter_products(ProductTable.query, pydantic_filter_by, _error_handler)
    query = sort_products(query, pydantic_sort_by, _error_handler)
    total = query.count()
    query = apply_range_to_query(query, after, first)

    products = query.all()
    has_next_page = len(products) > first

    products = products[:first]
    products_length = len(products)
    start_cursor = after if products_length else None
    end_cursor = after + products_length - 1
    page_products = [ProductType.from_pydantic(p) for p in products]

    return Connection(
        page=page_products,
        page_info=PageInfo(
            has_previous_page=bool(after),
            has_next_page=has_next_page,
            start_cursor=start_cursor,
            end_cursor=end_cursor,
            total_items=total if total else None,
        ),
    )
