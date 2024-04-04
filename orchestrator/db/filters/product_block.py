import structlog
from sqlalchemy import BinaryExpression

from orchestrator.db import ProductBlockTable, ProductTable, ResourceTypeTable
from orchestrator.db.filters import create_memoized_field_list, generic_filter_from_clauses
from orchestrator.db.filters.search_filters import default_inferred_column_clauses, node_to_str_val
from orchestrator.utils.search_query import Node

logger = structlog.get_logger(__name__)


def products_clause(node: Node) -> BinaryExpression:
    return ProductBlockTable.products.any(ProductTable.name.ilike(node_to_str_val(node)))


def resource_types_clause(node: Node) -> BinaryExpression:
    return ProductBlockTable.resource_types.any(ResourceTypeTable.resource_type.ilike(node_to_str_val(node)))


PRODUCT_BLOCK_TABLE_COLUMN_CLAUSES = default_inferred_column_clauses(ProductBlockTable) | {
    "product": products_clause,
    "resource_type": resource_types_clause,
}

product_block_filter_fields = create_memoized_field_list(PRODUCT_BLOCK_TABLE_COLUMN_CLAUSES)
filter_product_blocks = generic_filter_from_clauses(PRODUCT_BLOCK_TABLE_COLUMN_CLAUSES)
