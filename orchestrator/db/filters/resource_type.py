from typing import Callable

import structlog

from orchestrator.db import ProductBlockTable, ResourceTypeTable
from orchestrator.db.database import SearchQuery
from orchestrator.db.filters import generic_filter
from orchestrator.db.filters.generic_filters import generic_is_like_filter

logger = structlog.get_logger(__name__)


def product_blocks_filter(query: SearchQuery, value: str) -> SearchQuery:
    """Filter ResourceTypes by '-'-separated list of Product block 'name' (column) values."""
    product_blocks = value.split("-")
    return query.filter(ResourceTypeTable.product_blocks.any(ProductBlockTable.name.in_(product_blocks)))


RESOURCE_TYPE_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[SearchQuery, str], SearchQuery]] = {
    "resourceTypeId": generic_is_like_filter(ResourceTypeTable.resource_type_id),
    "resourceType": generic_is_like_filter(ResourceTypeTable.resource_type),
    "description": generic_is_like_filter(ResourceTypeTable.description),
    "productBlocks": product_blocks_filter,
}

filter_resource_types = generic_filter(RESOURCE_TYPE_FILTER_FUNCTIONS_BY_COLUMN)
