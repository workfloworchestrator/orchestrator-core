from typing import Union

import structlog
from graphql import GraphQLError

from orchestrator.db.filters import CallableErrorHander, Filter
from orchestrator.db.filters.product import filter_products
from orchestrator.db.models import ProductTable
from orchestrator.db.range.range import apply_range_to_query
from orchestrator.db.sorting.product import sort_products
from orchestrator.db.sorting.sorting import Sort
from orchestrator.graphql.pagination import Connection, PageInfo
from orchestrator.graphql.schemas.product import ProductType
from orchestrator.graphql.types import CustomInfo, GraphqlFilter, GraphqlSort

logger = structlog.get_logger(__name__)


def handle_product_error(info: CustomInfo) -> CallableErrorHander:
    def _handle_product_error(message: str, **kwargs) -> None:  # type: ignore
        logger.debug(message, **kwargs)
        extra_values = dict(kwargs.items()) if kwargs else {}
        info.context.errors.append(GraphQLError(message=message, path=info.path, extensions=extra_values))

    return _handle_product_error


async def resolve_products(
    info: CustomInfo,
    filter_by: Union[list[GraphqlFilter], None] = None,
    sort_by: Union[list[GraphqlSort], None] = None,
    first: int = 10,
    after: int = 0,
) -> Connection[ProductType]:
    _error_handler = handle_product_error(info)

    _range: Union[list[int], None] = [after, after + first] if after is not None and first else None
    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    logger.info("resolve_products() called", range=_range, sort=sort_by, filter=pydantic_filter_by)

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
