import structlog
from sqlalchemy import BinaryExpression, select

from orchestrator.db import ProductTable, WorkflowTable
from orchestrator.db.filters.filters import generic_filter_from_clauses
from orchestrator.db.filters.generic_filters import (
    generic_range_filters,
)
from orchestrator.db.filters.search_filters import default_inferred_column_clauses, inferred_filter
from orchestrator.db.filters.search_filters.inferred_filter import filter_exact
from orchestrator.utils.search_query import Node, WhereCondGenerator

logger = structlog.get_logger(__name__)

created_at_range_filters = generic_range_filters(WorkflowTable.created_at)


def make_product_clause(filter_generator: WhereCondGenerator) -> WhereCondGenerator:
    """The passed filter_generator takes a Node and returns a where clause acting on a ProductTable column."""

    def product_clause(node: Node) -> BinaryExpression:
        subq = select(WorkflowTable.workflow_id).join(WorkflowTable.products).where(filter_generator(node)).subquery()
        return WorkflowTable.workflow_id.in_(subq)

    return product_clause


WORKFLOW_TABLE_COLUMN_CLAUSES = default_inferred_column_clauses(WorkflowTable) | {
    "product": make_product_clause(inferred_filter(ProductTable.name)),
    "tag": make_product_clause(filter_exact(ProductTable.tag)),
}


workflow_filter_fields = list(WORKFLOW_TABLE_COLUMN_CLAUSES.keys())
filter_workflows = generic_filter_from_clauses(WORKFLOW_TABLE_COLUMN_CLAUSES)
