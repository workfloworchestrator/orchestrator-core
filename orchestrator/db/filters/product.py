import structlog
from sqlalchemy import BinaryExpression

from orchestrator.db import ProductBlockTable, ProductTable
from orchestrator.db.filters import generic_filter_from_clauses
from orchestrator.db.filters.search_filters import default_inferred_column_clauses, filter_exact, node_to_str_val
from orchestrator.utils.search_query import Node

logger = structlog.get_logger(__name__)


def product_block_clause(node: Node) -> BinaryExpression:
    return ProductTable.product_blocks.any(ProductBlockTable.name.ilike(node_to_str_val(node)))


PRODUCT_TABLE_COLUMN_CLAUSES = default_inferred_column_clauses(ProductTable) | {
    "product_block": product_block_clause,
    "tag": filter_exact(ProductTable.tag),
}

product_filter_fields = list(PRODUCT_TABLE_COLUMN_CLAUSES.keys())
filter_products = generic_filter_from_clauses(PRODUCT_TABLE_COLUMN_CLAUSES)
