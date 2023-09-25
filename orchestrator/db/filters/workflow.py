from typing import Callable

import structlog
from sqlalchemy.inspection import inspect

from orchestrator.db import ProductTable, WorkflowTable
from orchestrator.db.database import SearchQuery
from orchestrator.db.filters import generic_filter
from orchestrator.db.filters.generic_filters import generic_is_like_filter, generic_range_filters
from orchestrator.utils.helpers import to_camel

logger = structlog.get_logger(__name__)

created_at_range_filters = generic_range_filters(WorkflowTable.created_at)


def products_filter(query: SearchQuery, value: str) -> SearchQuery:
    """Filter ProductBlocks by '-'-separated list of Product 'name' (column) values."""
    products = value.split("-")
    return query.filter(WorkflowTable.products.any(ProductTable.name.in_(products)))


BASE_CAMEL = {to_camel(key): generic_is_like_filter(value) for key, value in inspect(WorkflowTable).columns.items()}

WORKFLOW_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[SearchQuery, str], SearchQuery]] = (
    BASE_CAMEL | {"products": products_filter} | created_at_range_filters
)

filter_workflows = generic_filter(WORKFLOW_FILTER_FUNCTIONS_BY_COLUMN)
