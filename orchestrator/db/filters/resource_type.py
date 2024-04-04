import structlog
from sqlalchemy import BinaryExpression

from orchestrator.db import ProductBlockTable, ResourceTypeTable
from orchestrator.db.filters import create_memoized_field_list, generic_filter_from_clauses
from orchestrator.db.filters.search_filters import default_inferred_column_clauses, node_to_str_val
from orchestrator.utils.search_query import Node

logger = structlog.get_logger(__name__)


def product_blocks_clause(node: Node) -> BinaryExpression:
    return ResourceTypeTable.product_blocks.any(ProductBlockTable.name.ilike(node_to_str_val(node)))


RESOURCE_TYPE_TABLE_COLUMN_CLAUSES = default_inferred_column_clauses(ResourceTypeTable) | {
    "product_block": product_blocks_clause,
}

resource_type_filter_fields = create_memoized_field_list(RESOURCE_TYPE_TABLE_COLUMN_CLAUSES)
filter_resource_types = generic_filter_from_clauses(RESOURCE_TYPE_TABLE_COLUMN_CLAUSES)
