from orchestrator.db import SubscriptionTable
from orchestrator.db.sorting.sorting import generic_sort

VALID_SORT_KEY_LIST = [
    "subscription_id",
    "product_id",
    "name",
    "description",
    "insync",
    "status",
    "note",
    "tag",
    "start_date",
    "end_date",
]
VALID_SORT_KEY_MAP = {key: key for key in VALID_SORT_KEY_LIST}

sort_subscriptions = generic_sort(VALID_SORT_KEY_MAP, SubscriptionTable)
