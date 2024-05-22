from collections.abc import Callable

from sqlalchemy import Column, Select
from sqlalchemy.inspection import inspect
from sqlalchemy.sql import expression

from orchestrator.db import ProcessSubscriptionTable, ProcessTable, ProductTable, SubscriptionTable, WorkflowTable
from orchestrator.db.filters import create_memoized_field_list
from orchestrator.db.sorting import QueryType, SortOrder, generic_column_sort, generic_sort
from orchestrator.utils.helpers import to_camel

PROCESS_CAMEL_SORT = {
    to_camel(key): generic_column_sort(value, ProcessTable) for key, value in inspect(ProcessTable).columns.items()
}
PROCESS_SNAKE_SORT = {
    key: generic_column_sort(value, ProcessTable) for key, value in inspect(ProcessTable).columns.items()
}


def generic_process_relation_sort(
    field: Column, join_tables: list | None = None
) -> Callable[[QueryType, SortOrder], QueryType]:
    join_tables = join_tables or []

    def sort_function(query: QueryType, order: SortOrder) -> QueryType:
        # SQLAlchemy can't resolve the query correctly when we join the same table multiple times. A refactor for the sorting logic that
        # ensures each table is joined once for the sort order is required. For now, we access an internal member `_setup_join` to check whether a table
        # has already been joined
        if isinstance(query, Select):
            joined_tables = [str(t[0]) for t in query._setup_joins]

            for table in join_tables:
                if (tablename := getattr(table, "__tablename__", "")) and tablename not in joined_tables:
                    query = query.join(table)

        order_by_expr = expression.desc if order == SortOrder.DESC else expression.asc
        return query.order_by(order_by_expr(field))

    return sort_function


PROCESS_PRODUCT_SORT = {
    to_camel(key if "product" in key else f"product_{key}"): generic_process_relation_sort(
        value, [ProcessSubscriptionTable, SubscriptionTable, ProductTable]
    )
    for key, value in inspect(ProductTable).columns.items()
}


PROCESS_SORT_FUNCTIONS_BY_COLUMN = (
    PROCESS_PRODUCT_SORT
    | PROCESS_CAMEL_SORT
    | PROCESS_SNAKE_SORT
    | {
        "workflowName": generic_process_relation_sort(WorkflowTable.name, [WorkflowTable]),
        "workflowTarget": generic_process_relation_sort(WorkflowTable.target, [WorkflowTable]),
        "subscriptions": generic_process_relation_sort(
            SubscriptionTable.description, [ProcessSubscriptionTable, SubscriptionTable]
        ),
    }
)
process_sort_fields = create_memoized_field_list(PROCESS_SORT_FUNCTIONS_BY_COLUMN)
sort_processes = generic_sort(PROCESS_SORT_FUNCTIONS_BY_COLUMN)
