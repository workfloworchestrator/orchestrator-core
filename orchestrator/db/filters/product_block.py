from collections.abc import Callable

import structlog
from sqlalchemy import BinaryExpression

from orchestrator.db import ProductBlockTable, ProductTable, ResourceTypeTable
from orchestrator.db.filters import QueryType, generic_filter
from orchestrator.db.filters.generic_filters import (
    generic_is_like_filter,
    generic_range_filters,
    generic_values_in_column_filter,
)
from orchestrator.db.filters.search_filters import default_inferred_column_clauses, node_to_str_val
from orchestrator.utils.search_query import Node

logger = structlog.get_logger(__name__)


def products_filter(query: QueryType, value: str) -> QueryType:
    """Filter ProductBlocks by '-'-separated list of Product 'name' (column) values."""
    products = value.split("-")
    return query.filter(ProductBlockTable.products.any(ProductTable.name.in_(products)))


def products_clause(node: Node) -> BinaryExpression:
    return ProductBlockTable.products.any(ProductTable.name.ilike(node_to_str_val(node)))


def resource_types_filter(query: QueryType, value: str) -> QueryType:
    """Filter ProductBlocks by '-'-separated list of Resource Type 'resource_type' (column) values."""
    resource_types = value.split("-")
    return query.filter(ProductBlockTable.resource_types.any(ResourceTypeTable.resource_type.in_(resource_types)))


def resource_types_clause(node: Node) -> BinaryExpression:
    return ProductBlockTable.resource_types.any(ResourceTypeTable.resource_type.ilike(node_to_str_val(node)))


created_at_range_filters = generic_range_filters(ProductBlockTable.created_at)
end_date_range_filters = generic_range_filters(ProductBlockTable.end_date)

PRODUCT_BLOCK_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[QueryType, str], QueryType]] = (
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

PRODUCT_BLOCK_TABLE_COLUMN_CLAUSES = default_inferred_column_clauses(ProductBlockTable) | {
    # "product": products_clause,
    "resource_type": resource_types_clause,
    "resourceType": resource_types_clause,
}

product_block_filter_fields = list(PRODUCT_BLOCK_FILTER_FUNCTIONS_BY_COLUMN.keys())
filter_product_blocks = generic_filter(PRODUCT_BLOCK_FILTER_FUNCTIONS_BY_COLUMN)
