from typing import Union

import structlog

from orchestrator.db.filters.filters import Filter
from orchestrator.db.models import ProductTable
from orchestrator.db.sorting.sorting import Sort
from orchestrator.graphql.schemas.product import ProductType
from orchestrator.graphql.types import CustomInfo, GraphqlFilter, GraphqlSort

logger = structlog.get_logger(__name__)


async def resolve_products(
    info: CustomInfo,
    filter_by: Union[list[GraphqlFilter], None] = None,
    sort_by: Union[list[GraphqlSort], None] = None,
    first: int = 10,
    after: int = 0,
) -> list[ProductType]:
    _range: list[int] | None = [after, after + first] if after is not None and first else None
    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    logger.info("resolve_products() called", range=_range, sort=sort_by, filter=pydantic_filter_by)
    logger.debug("pydantic_sort_by: ", pydantic_sort_by=pydantic_sort_by)

    results = ProductTable.query.all()

    return [ProductType.from_pydantic(p) for p in results]
