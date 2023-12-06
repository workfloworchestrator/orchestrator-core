from typing import Callable

import structlog
from sqlalchemy import BinaryExpression
from sqlalchemy.inspection import inspect

from orchestrator.db import ProductTable, WorkflowTable
from orchestrator.db.filters import QueryType, generic_filter
from orchestrator.db.filters.generic_filters import (
    generic_is_like_filter,
    generic_range_filters,
)
from orchestrator.db.filters.search_filters import default_inferred_column_clauses, node_to_str_val
from orchestrator.utils.helpers import to_camel
from orchestrator.utils.search_query import Node

logger = structlog.get_logger(__name__)

created_at_range_filters = generic_range_filters(WorkflowTable.created_at)


def products_filter(query: QueryType, value: str) -> QueryType:
    """Filter ProductBlocks by '-'-separated list of Product 'name' (column) values."""
    products = value.split("-")
    return query.filter(WorkflowTable.products.any(ProductTable.name.in_(products)))


def products_clause(node: Node) -> BinaryExpression:
    return WorkflowTable.products.any(ProductTable.name.ilike(node_to_str_val(node)))


BASE_CAMEL = {to_camel(key): generic_is_like_filter(value) for key, value in inspect(WorkflowTable).columns.items()}

WORKFLOW_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[QueryType, str], QueryType]] = (
    BASE_CAMEL | {"products": products_filter} | created_at_range_filters
)


WORKFLOW_TABLE_COLUMN_CLAUSES = default_inferred_column_clauses(WorkflowTable) | {"product": products_clause}


workflow_filter_fields = list(WORKFLOW_FILTER_FUNCTIONS_BY_COLUMN.keys())
filter_workflows = generic_filter(WORKFLOW_FILTER_FUNCTIONS_BY_COLUMN)
