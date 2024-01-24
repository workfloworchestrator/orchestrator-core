from sqlalchemy.inspection import inspect

from orchestrator.db import WorkflowTable
from orchestrator.db.sorting.sorting import generic_column_sort, generic_sort
from orchestrator.utils.helpers import to_camel

WORKFLOW_SORT_FUNCTIONS_BY_COLUMN = {
    to_camel(key): generic_column_sort(value, WorkflowTable) for key, value in inspect(WorkflowTable).columns.items()
}

workflow_sort_fields = list(WORKFLOW_SORT_FUNCTIONS_BY_COLUMN.keys())
sort_workflows = generic_sort(WORKFLOW_SORT_FUNCTIONS_BY_COLUMN)
