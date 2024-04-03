import structlog
from sqlalchemy import BinaryExpression, select

from orchestrator.db import ProductTable, WorkflowTable
from orchestrator.db.filters import create_memoized_field_list, generic_filter_from_clauses
from orchestrator.db.filters.search_filters import default_inferred_column_clauses, filter_exact, inferred_filter
from orchestrator.utils.search_query import Node, WhereCondGenerator

logger = structlog.get_logger(__name__)


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


workflow_filter_fields = create_memoized_field_list(WORKFLOW_TABLE_COLUMN_CLAUSES)
filter_workflows = generic_filter_from_clauses(WORKFLOW_TABLE_COLUMN_CLAUSES)
