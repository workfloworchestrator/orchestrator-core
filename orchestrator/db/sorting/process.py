from typing import Callable

from sqlalchemy import Column
from sqlalchemy.inspection import inspect
from sqlalchemy.sql import expression

from orchestrator.db import ProcessSubscriptionTable, ProcessTable, ProductTable, SubscriptionTable
from orchestrator.db.database import SearchQuery
from orchestrator.db.sorting.sorting import SortOrder, generic_column_sort, generic_sort
from orchestrator.utils.helpers import to_camel

PROCESS_CAMEL_SORT = {to_camel(key): generic_column_sort(value) for key, value in inspect(ProcessTable).columns.items()}
PROCESS_SNAKE_SORT = {key: generic_column_sort(value) for key, value in inspect(ProcessTable).columns.items()}


def generic_process_product_sort(field: Column) -> Callable[[SearchQuery, SortOrder], SearchQuery]:
    def sort_function(query: SearchQuery, order: SortOrder) -> SearchQuery:
        joined_query = query.join(ProcessSubscriptionTable).join(SubscriptionTable).join(ProductTable)
        if order == SortOrder.DESC:
            return joined_query.order_by(expression.desc(field))
        return joined_query.order_by(expression.asc(field))

    return sort_function


PROCESS_PRODUCT_SORT = {
    to_camel(key if "product" in key else f"product_{key}"): generic_process_product_sort(value)
    for key, value in inspect(ProductTable).columns.items()
}


PROCESS_SORT_FUNCTIONS_BY_COLUMN = (
    PROCESS_PRODUCT_SORT
    | PROCESS_CAMEL_SORT
    | PROCESS_SNAKE_SORT
    | {
        "workflow": generic_column_sort(ProcessTable.workflow_name),  # TODO: deprecated, remove in 1.4
        "status": generic_column_sort(ProcessTable.last_status),  # TODO: deprecated, remove in 1.4
        "creator": generic_column_sort(ProcessTable.created_by),  # TODO: deprecated, remove in 1.4
        "started": generic_column_sort(ProcessTable.started_at),  # TODO: deprecated, remove in 1.4
        "modified": generic_column_sort(ProcessTable.last_modified_at),  # TODO: deprecated, remove in 1.4
    }
)

sort_processes = generic_sort(PROCESS_SORT_FUNCTIONS_BY_COLUMN)
