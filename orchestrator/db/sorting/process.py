from sqlalchemy.inspection import inspect

from orchestrator.db import ProcessTable
from orchestrator.db.sorting.sorting import generic_column_sort, generic_sort
from orchestrator.utils.helpers import to_camel

VALID_SORT_KEY_MAP = {
    "created_by": "created_by",
    "started_at": "started",
    "last_status": "status",
    "last_modified_at": "modified",
}
PROCESS_SORT_FUNCTIONS_BY_COLUMN = {
    to_camel(VALID_SORT_KEY_MAP.get(key, key)): generic_column_sort(value)
    for [key, value] in inspect(ProcessTable).columns.items()
}

sort_processes = generic_sort(PROCESS_SORT_FUNCTIONS_BY_COLUMN)
