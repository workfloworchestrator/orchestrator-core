from collections.abc import Callable

import structlog
from sqlalchemy import BinaryExpression, select
from sqlalchemy.inspection import inspect

from orchestrator.db import ProductTable, WorkflowTable
from orchestrator.db.filters import QueryType, generic_filter
from orchestrator.db.filters.generic_filters import (
    generic_is_like_filter,
    generic_range_filters,
)
from orchestrator.db.filters.search_filters import default_inferred_column_clauses, inferred_filter
from orchestrator.db.filters.search_filters.inferred_filter import filter_exact
from orchestrator.utils.helpers import to_camel
from orchestrator.utils.search_query import Node, WhereCondGenerator

logger = structlog.get_logger(__name__)

created_at_range_filters = generic_range_filters(WorkflowTable.created_at)


def products_filter(query: QueryType, value: str) -> QueryType:
    """Filter ProductBlocks by '-'-separated list of Product 'name' (column) values."""
    products = value.split("-")
    return query.filter(WorkflowTable.products.any(ProductTable.name.in_(products)))


def make_product_clause(filter_generator: WhereCondGenerator) -> WhereCondGenerator:
    """The passed filter_generator takes a Node and returns a where clause acting on a ProductTable column."""

    def product_clause(node: Node) -> BinaryExpression:
        subq = select(WorkflowTable.workflow_id).join(WorkflowTable.products).where(filter_generator(node)).subquery()
        return WorkflowTable.workflow_id.in_(subq)

    return product_clause


BASE_CAMEL = {to_camel(key): generic_is_like_filter(value) for key, value in inspect(WorkflowTable).columns.items()}

WORKFLOW_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[QueryType, str], QueryType]] = (
    BASE_CAMEL | {"products": products_filter} | created_at_range_filters
)


WORKFLOW_TABLE_COLUMN_CLAUSES = default_inferred_column_clauses(WorkflowTable) | {
    "product": make_product_clause(inferred_filter(ProductTable.name)),
    "tag": make_product_clause(filter_exact(ProductTable.tag)),
}


workflow_filter_fields = list(WORKFLOW_FILTER_FUNCTIONS_BY_COLUMN.keys())
filter_workflows = generic_filter(WORKFLOW_FILTER_FUNCTIONS_BY_COLUMN)
