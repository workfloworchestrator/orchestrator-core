from collections.abc import Callable

import structlog
from sqlalchemy import BinaryExpression, inspect
from sqlalchemy.orm import MappedColumn

from orchestrator.db import ProductBlockTable, ResourceTypeTable
from orchestrator.db.filters import QueryType, generic_filter
from orchestrator.db.filters.generic_filters import generic_is_like_filter
from orchestrator.db.filters.search_filters import default_inferred_column_clauses, node_to_str_val
from orchestrator.utils.helpers import to_camel
from orchestrator.utils.search_query import Node

logger = structlog.get_logger(__name__)


def product_blocks_filter(query: QueryType, value: str) -> QueryType:
    """Filter ResourceTypes by '-'-separated list of Product block 'name' (column) values."""
    product_blocks = value.split("-")
    return query.filter(ResourceTypeTable.product_blocks.any(ProductBlockTable.name.in_(product_blocks)))


def product_blocks_clause(node: Node) -> BinaryExpression:
    return ResourceTypeTable.product_blocks.any(ProductBlockTable.name.ilike(node_to_str_val(node)))


RESOURCE_TYPE_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[QueryType, str], QueryType]] = {
    "resourceTypeId": generic_is_like_filter(ResourceTypeTable.resource_type_id),
    "resourceType": generic_is_like_filter(ResourceTypeTable.resource_type),
    "description": generic_is_like_filter(ResourceTypeTable.description),
    "productBlocks": product_blocks_filter,
}

RESOURCE_TYPE_TABLE_COLUMN_MAPPINGS: dict[str, MappedColumn] = {
    k: column for key, column in inspect(ResourceTypeTable).columns.items() for k in [key, to_camel(key)]
} | {"product_block": ProductBlockTable.name, "productBlock": ProductBlockTable.name}
resource_type_filter_fields = list(RESOURCE_TYPE_FILTER_FUNCTIONS_BY_COLUMN.keys())
filter_resource_types = generic_filter(RESOURCE_TYPE_FILTER_FUNCTIONS_BY_COLUMN)

RESOURCE_TYPE_TABLE_COLUMN_CLAUSES = default_inferred_column_clauses(ResourceTypeTable) | {
    "product_block": product_blocks_clause,
    "productBlock": product_blocks_clause,
}
