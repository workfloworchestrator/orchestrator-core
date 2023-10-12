from typing import Callable

import structlog
from sqlalchemy.inspection import inspect

from orchestrator.db import ProductTable, WorkflowTable
from orchestrator.db.filters import QueryType, generic_filter
from orchestrator.db.filters.generic_filters import generic_is_like_filter, generic_range_filters
from orchestrator.utils.helpers import to_camel

logger = structlog.get_logger(__name__)

created_at_range_filters = generic_range_filters(WorkflowTable.created_at)


def products_filter(query: QueryType, value: str) -> QueryType:
    """Filter ProductBlocks by '-'-separated list of Product 'name' (column) values."""
    products = value.split("-")
    return query.filter(WorkflowTable.products.any(ProductTable.name.in_(products)))


BASE_CAMEL = {to_camel(key): generic_is_like_filter(value) for key, value in inspect(WorkflowTable).columns.items()}

WORKFLOW_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[QueryType, str], QueryType]] = (
    BASE_CAMEL | {"products": products_filter} | created_at_range_filters
)

workflow_filter_fields = list(WORKFLOW_FILTER_FUNCTIONS_BY_COLUMN.keys())
filter_workflows = generic_filter(WORKFLOW_FILTER_FUNCTIONS_BY_COLUMN)
