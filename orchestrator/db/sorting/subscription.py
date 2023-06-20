from sqlalchemy.inspection import inspect

from orchestrator.db import SubscriptionTable
from orchestrator.db.sorting.product import PRODUCT_SORT_FUNCTIONS_BY_COLUMN
from orchestrator.db.sorting.sorting import generic_column_sort, generic_sort
from orchestrator.utils.helpers import to_camel

subscription_table_sort = {
    to_camel(key): generic_column_sort(value) for [key, value] in inspect(SubscriptionTable).columns.items()
}

SUBSCRIPTION_SORT_FUNCTIONS_BY_COLUMN = PRODUCT_SORT_FUNCTIONS_BY_COLUMN | subscription_table_sort

sort_subscriptions = generic_sort(SUBSCRIPTION_SORT_FUNCTIONS_BY_COLUMN)
