from collections.abc import Callable

import structlog
from sqlalchemy import BinaryExpression

from orchestrator.db import ProductBlockTable, ProductTable
from orchestrator.db.filters import QueryType, generic_filter
from orchestrator.db.filters.generic_filters import (
    generic_is_like_filter,
    generic_values_in_column_filter,
)
from orchestrator.db.filters.search_filters import default_inferred_column_clauses, node_to_str_val
from orchestrator.db.filters.search_filters.inferred_filter import filter_exact
from orchestrator.utils.search_query import Node

logger = structlog.get_logger(__name__)


def product_block_filter(query: QueryType, value: str) -> QueryType:
    """Filter ProductBlocks by '-'-separated list of Product block 'name' (column) values."""
    blocks = value.split("-")
    return query.filter(ProductTable.product_blocks.any(ProductBlockTable.name.in_(blocks)))


def product_block_clause(node: Node) -> BinaryExpression:
    return ProductTable.product_blocks.any(ProductBlockTable.name.ilike(node_to_str_val(node)))


PRODUCT_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[QueryType, str], QueryType]] = {
    "product_id": generic_is_like_filter(ProductTable.product_id),
    "name": generic_is_like_filter(ProductTable.name),
    "description": generic_is_like_filter(ProductTable.description),
    "product_type": generic_is_like_filter(ProductTable.product_type),
    "status": generic_values_in_column_filter(ProductTable.status),
    "tag": generic_values_in_column_filter(ProductTable.tag),
    "product_blocks": product_block_filter,
}

PRODUCT_TABLE_COLUMN_CLAUSES = default_inferred_column_clauses(ProductTable) | {
    "productBlock": product_block_clause,
    "product_block": product_block_clause,
    "tag": filter_exact(ProductTable.tag),
}

product_filter_fields = list(PRODUCT_FILTER_FUNCTIONS_BY_COLUMN.keys())
filter_products = generic_filter(PRODUCT_FILTER_FUNCTIONS_BY_COLUMN)
