from collections.abc import Callable

from sqlalchemy import Column
from sqlalchemy.inspection import inspect
from sqlalchemy.sql import expression

from orchestrator.db import ProductTable, SubscriptionTable
from orchestrator.db.filters import create_memoized_field_list
from orchestrator.db.sorting import QueryType, SortOrder, generic_column_sort, generic_sort
from orchestrator.utils.helpers import to_camel


def generic_subscription_relation_sort(field: Column) -> Callable[[QueryType, SortOrder], QueryType]:
    def sort_function(query: QueryType, order: SortOrder) -> QueryType:
        if order == SortOrder.DESC:
            return query.order_by(expression.desc(field))
        return query.order_by(expression.asc(field))

    return sort_function


SUBSCRIPTION_PRODUCT_SORT = {
    to_camel(key if "product" in key else f"product_{key}"): generic_subscription_relation_sort(value)
    for key, value in inspect(ProductTable).columns.items()
}

subscription_table_sort = {
    to_camel(key): generic_column_sort(value, SubscriptionTable)
    for [key, value] in inspect(SubscriptionTable).columns.items()
}

SUBSCRIPTION_SORT_FUNCTIONS_BY_COLUMN = (
    SUBSCRIPTION_PRODUCT_SORT | subscription_table_sort | {"tag": SUBSCRIPTION_PRODUCT_SORT["productTag"]}
)


subscription_sort_fields = create_memoized_field_list(SUBSCRIPTION_SORT_FUNCTIONS_BY_COLUMN)
sort_subscriptions = generic_sort(SUBSCRIPTION_SORT_FUNCTIONS_BY_COLUMN)
