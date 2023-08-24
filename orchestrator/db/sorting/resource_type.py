from sqlalchemy.inspection import inspect

from orchestrator.db import ResourceTypeTable
from orchestrator.db.sorting.sorting import generic_column_sort, generic_sort
from orchestrator.utils.helpers import to_camel

RESOURCE_TYPE_SORT_FUNCTIONS_BY_COLUMN = {
    to_camel(key): generic_column_sort(value) for key, value in inspect(ResourceTypeTable).columns.items()
}

sort_resource_types = generic_sort(RESOURCE_TYPE_SORT_FUNCTIONS_BY_COLUMN)
