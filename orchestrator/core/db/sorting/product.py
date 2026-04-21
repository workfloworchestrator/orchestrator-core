from sqlalchemy.inspection import inspect

from orchestrator.core.db import ProductTable
from orchestrator.core.db.filters import create_memoized_field_list
from orchestrator.core.db.sorting import generic_column_sort, generic_sort
from orchestrator.core.utils.helpers import to_camel

PRODUCT_SORT_FUNCTIONS_BY_COLUMN = {
    to_camel(key): generic_column_sort(value, ProductTable) for [key, value] in inspect(ProductTable).columns.items()
}

product_sort_fields = create_memoized_field_list(PRODUCT_SORT_FUNCTIONS_BY_COLUMN)
sort_products = generic_sort(PRODUCT_SORT_FUNCTIONS_BY_COLUMN)
