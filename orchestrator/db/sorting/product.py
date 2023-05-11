from orchestrator.db import ProductTable
from orchestrator.db.sorting.sorting import generic_sort

VALID_SORT_KEY_MAP = {
    "created_at": "created_at",
    "end_date": "end_date",
    "status": "status",
    "product_type": "product_type",
    "name": "name",
    "tag": "tag",
}

sort_products = generic_sort(VALID_SORT_KEY_MAP, ProductTable)
