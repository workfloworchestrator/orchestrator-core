from sqlalchemy.inspection import inspect

from orchestrator.core.db import ProductBlockTable
from orchestrator.core.db.filters import create_memoized_field_list
from orchestrator.core.db.sorting import generic_column_sort, generic_sort
from orchestrator.core.utils.helpers import to_camel

PRODUCT_BLOCK_SORT_FUNCTIONS_BY_COLUMN = {
    to_camel(key): generic_column_sort(value, ProductBlockTable)
    for key, value in inspect(ProductBlockTable).columns.items()
}

product_block_sort_fields = create_memoized_field_list(PRODUCT_BLOCK_SORT_FUNCTIONS_BY_COLUMN)
sort_product_blocks = generic_sort(PRODUCT_BLOCK_SORT_FUNCTIONS_BY_COLUMN)
