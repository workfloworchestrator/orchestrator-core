from sqlalchemy.inspection import inspect

from orchestrator.core.db import WorkflowTable
from orchestrator.core.db.filters import create_memoized_field_list
from orchestrator.core.db.sorting import generic_column_sort, generic_sort
from orchestrator.core.utils.helpers import to_camel

WORKFLOW_SORT_FUNCTIONS_BY_COLUMN = {
    to_camel(key): generic_column_sort(value, WorkflowTable) for key, value in inspect(WorkflowTable).columns.items()
}

workflow_sort_fields = create_memoized_field_list(WORKFLOW_SORT_FUNCTIONS_BY_COLUMN)
sort_workflows = generic_sort(WORKFLOW_SORT_FUNCTIONS_BY_COLUMN)
