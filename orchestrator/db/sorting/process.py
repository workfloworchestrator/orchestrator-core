from collections.abc import Callable

from sqlalchemy import Column, Select
from sqlalchemy.inspection import inspect
from sqlalchemy.sql import expression

from orchestrator.db import ProcessSubscriptionTable, ProcessTable, ProductTable, SubscriptionTable, WorkflowTable
from orchestrator.db.sorting.sorting import QueryType, SortOrder, generic_column_sort, generic_sort
from orchestrator.utils.helpers import to_camel

PROCESS_CAMEL_SORT = {
    to_camel(key): generic_column_sort(value, ProcessTable) for key, value in inspect(ProcessTable).columns.items()
}
PROCESS_SNAKE_SORT = {
    key: generic_column_sort(value, ProcessTable) for key, value in inspect(ProcessTable).columns.items()
}


def generic_process_relation_sort(field: Column) -> Callable[[QueryType, SortOrder], QueryType]:
    def sort_function(query: QueryType, order: SortOrder) -> QueryType:
        if isinstance(query, Select):
            joined_query: QueryType = query.join(ProcessSubscriptionTable).join(SubscriptionTable).join(ProductTable)
        else:
            # Can't join on CompoundSelect
            joined_query = query
        if order == SortOrder.DESC:
            return joined_query.order_by(expression.desc(field))
        return joined_query.order_by(expression.asc(field))

    return sort_function


PROCESS_PRODUCT_SORT = {
    to_camel(key if "product" in key else f"product_{key}"): generic_process_relation_sort(value)
    for key, value in inspect(ProductTable).columns.items()
}


PROCESS_SORT_FUNCTIONS_BY_COLUMN = (
    PROCESS_PRODUCT_SORT
    | PROCESS_CAMEL_SORT
    | PROCESS_SNAKE_SORT
    | {
        "workflowTarget": generic_process_relation_sort(ProcessSubscriptionTable.workflow_target),
        "subscriptions": generic_process_relation_sort(SubscriptionTable.description),
        "workflow": generic_process_relation_sort(WorkflowTable.name),  # TODO: deprecated, remove in 1.4
        "status": generic_column_sort(ProcessTable.last_status, ProcessTable),  # TODO: deprecated, remove in 1.4
        "creator": generic_column_sort(ProcessTable.created_by, ProcessTable),  # TODO: deprecated, remove in 1.4
        "started": generic_column_sort(ProcessTable.started_at, ProcessTable),  # TODO: deprecated, remove in 1.4
        "modified": generic_column_sort(ProcessTable.last_modified_at, ProcessTable),  # TODO: deprecated, remove in 1.4
    }
)
process_sort_fields = list(PROCESS_SORT_FUNCTIONS_BY_COLUMN.keys())
sort_processes = generic_sort(PROCESS_SORT_FUNCTIONS_BY_COLUMN)
