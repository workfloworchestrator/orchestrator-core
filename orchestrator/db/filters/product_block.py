from typing import Callable

import structlog

from orchestrator.db import ProductBlockTable, ProductTable, ResourceTypeTable
from orchestrator.db.database import SearchQuery
from orchestrator.db.filters import generic_filter
from orchestrator.db.filters.generic_filters import (
    generic_is_like_filter,
    generic_range_filters,
    generic_values_in_column_filter,
)

logger = structlog.get_logger(__name__)


def products_filter(query: SearchQuery, value: str) -> SearchQuery:
    """Filter ProductBlocks by '-'-separated list of Product 'name' (column) values."""
    products = value.split("-")
    return query.filter(ProductBlockTable.products.any(ProductTable.name.in_(products)))


def resource_types_filter(query: SearchQuery, value: str) -> SearchQuery:
    """Filter ProductBlocks by '-'-separated list of Resource Type 'resource_type' (column) values."""
    resource_types = value.split("-")
    return query.filter(ProductBlockTable.resource_types.any(ResourceTypeTable.resource_type.in_(resource_types)))


created_at_range_filters = generic_range_filters(ProductBlockTable.created_at)
end_date_range_filters = generic_range_filters(ProductBlockTable.end_date)

PRODUCT_BLOCK_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[SearchQuery, str], SearchQuery]] = (
    {
        "product_block_id": generic_is_like_filter(ProductBlockTable.product_block_id),
        "name": generic_is_like_filter(ProductBlockTable.name),
        "description": generic_is_like_filter(ProductBlockTable.description),
        "tag": generic_values_in_column_filter(ProductBlockTable.tag),
        "status": generic_values_in_column_filter(ProductBlockTable.status),
        "products": products_filter,
        "resource_types": resource_types_filter,
    }
    | created_at_range_filters
    | end_date_range_filters
)

filter_product_blocks = generic_filter(PRODUCT_BLOCK_FILTER_FUNCTIONS_BY_COLUMN)
