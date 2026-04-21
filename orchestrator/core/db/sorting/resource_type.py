from sqlalchemy.inspection import inspect

from orchestrator.core.db import ResourceTypeTable
from orchestrator.core.db.filters import create_memoized_field_list
from orchestrator.core.db.sorting import generic_column_sort, generic_sort
from orchestrator.core.utils.helpers import to_camel

RESOURCE_TYPE_SORT_FUNCTIONS_BY_COLUMN = {
    to_camel(key): generic_column_sort(value, ResourceTypeTable)
    for key, value in inspect(ResourceTypeTable).columns.items()
}

resource_type_sort_fields = create_memoized_field_list(RESOURCE_TYPE_SORT_FUNCTIONS_BY_COLUMN)
sort_resource_types = generic_sort(RESOURCE_TYPE_SORT_FUNCTIONS_BY_COLUMN)
