from sqlalchemy.inspection import inspect

from orchestrator.db import ProductTable
from orchestrator.db.sorting.sorting import generic_column_sort, generic_sort
from orchestrator.utils.helpers import to_camel

PRODUCT_SORT_FUNCTIONS_BY_COLUMN = {
    to_camel(key): generic_column_sort(value, ProductTable) for [key, value] in inspect(ProductTable).columns.items()
}

product_sort_fields = list(PRODUCT_SORT_FUNCTIONS_BY_COLUMN.keys())
sort_products = generic_sort(PRODUCT_SORT_FUNCTIONS_BY_COLUMN)
