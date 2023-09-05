from sqlalchemy.inspection import inspect

from orchestrator.db import ProcessTable
from orchestrator.db.sorting.product import PRODUCT_SORT_FUNCTIONS_BY_COLUMN
from orchestrator.db.sorting.sorting import generic_column_sort, generic_sort
from orchestrator.utils.helpers import to_camel

PROCESS_CAMEL_SORT = {to_camel(key): generic_column_sort(value) for key, value in inspect(ProcessTable).columns.items()}
PROCESS_SNAKE_SORT = {key: generic_column_sort(value) for key, value in inspect(ProcessTable).columns.items()}
PROCESS_PRODUCT_SORT = {
    to_camel(key if "product" in key else f"product_{key}"): value
    for key, value in PRODUCT_SORT_FUNCTIONS_BY_COLUMN.items()
}

PROCESS_SORT_FUNCTIONS_BY_COLUMN = PROCESS_PRODUCT_SORT | PROCESS_SNAKE_SORT | PROCESS_CAMEL_SORT
PROCESS_SORT_FUNCTIONS_BY_COLUMN["workflow"] = generic_column_sort(
    ProcessTable.workflow_name
)  # TODO: deprecated, remove in 1.3
PROCESS_SORT_FUNCTIONS_BY_COLUMN["status"] = generic_column_sort(
    ProcessTable.last_status
)  # TODO: deprecated, remove in 1.3
PROCESS_SORT_FUNCTIONS_BY_COLUMN["creator"] = generic_column_sort(
    ProcessTable.created_by
)  # TODO: deprecated, remove in 1.3
PROCESS_SORT_FUNCTIONS_BY_COLUMN["started"] = generic_column_sort(
    ProcessTable.started_at
)  # TODO: deprecated, remove in 1.3
PROCESS_SORT_FUNCTIONS_BY_COLUMN["modified"] = generic_column_sort(
    ProcessTable.last_modified_at
)  # TODO: deprecated, remove in 1.3

sort_processes = generic_sort(PROCESS_SORT_FUNCTIONS_BY_COLUMN)
