from typing import Callable

import structlog

from orchestrator.db import ProductTable, WorkflowTable
from orchestrator.db.database import SearchQuery
from orchestrator.db.filters import generic_filter
from orchestrator.db.filters.generic_filters import generic_is_like_filter, generic_range_filters

logger = structlog.get_logger(__name__)

start_date_range_filters = generic_range_filters(WorkflowTable.created_at)


def products_filter(query: SearchQuery, value: str) -> SearchQuery:
    """Filter ProductBlocks by '-'-separated list of Product 'name' (column) values."""
    products = value.split("-")
    return query.filter(WorkflowTable.products.any(ProductTable.name.in_(products)))


WORKFLOW_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[SearchQuery, str], SearchQuery]] = {
    "workflowId": generic_is_like_filter(WorkflowTable.workflow_id),
    "name": generic_is_like_filter(WorkflowTable.name),
    "description": generic_is_like_filter(WorkflowTable.description),
    "createdAt": generic_is_like_filter(WorkflowTable.created_at),
    "products": products_filter,
} | start_date_range_filters

filter_workflows = generic_filter(WORKFLOW_FILTER_FUNCTIONS_BY_COLUMN)
