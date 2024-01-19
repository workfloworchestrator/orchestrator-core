# Copyright 2019-2023 SURF.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections.abc import Callable

import structlog
from sqlalchemy import func

from orchestrator.api.helpers import _process_text_query, add_subscription_search_query_filter
from orchestrator.db import ProductTable, SubscriptionTable
from orchestrator.db.filters.filters import QueryType, generic_filter
from orchestrator.db.filters.generic_filters import (
    generic_bool_filter,
    generic_is_like_filter,
    generic_range_filters,
    generic_values_in_column_filter,
)
from orchestrator.db.models import SubscriptionSearchView

logger = structlog.get_logger(__name__)


def tsv_filter(query: QueryType, value: str) -> QueryType:
    # Quote key:value tokens. This will use the FOLLOWED BY operator (https://www.postgresql.org/docs/13/textsearch-controls.html)
    processed_text_query = _process_text_query(value)

    logger.debug("Running full-text search query:", value=processed_text_query)
    # TODO: Make 'websearch_to_tsquery' into a sqlalchemy extension
    return query.join(SubscriptionSearchView).filter(
        func.websearch_to_tsquery("simple", processed_text_query).op("@@")(SubscriptionSearchView.tsv)
    )


def subscription_list_filter(query: QueryType, value: str) -> QueryType:
    values = [s.lower() for s in value.split(",")]
    return query.filter(SubscriptionTable.subscription_id.in_(values))


status_filter = generic_values_in_column_filter(SubscriptionTable.status)
product_filter = generic_values_in_column_filter(ProductTable.name)
tags_filter = generic_values_in_column_filter(ProductTable.tag)

start_date_range_filters = generic_range_filters(SubscriptionTable.start_date)
end_date_range_filters = generic_range_filters(SubscriptionTable.end_date)


SUBSCRIPTION_FILTER_FUNCTIONS_BY_COLUMN: dict[str, Callable[[QueryType, str], QueryType]] = (
    {
        "subscriptionId": generic_is_like_filter(SubscriptionTable.subscription_id),
        "subscriptionIds": subscription_list_filter,
        "description": generic_is_like_filter(SubscriptionTable.description),
        "status": status_filter,
        "product": product_filter,
        "insync": generic_bool_filter(SubscriptionTable.insync),
        "note": generic_is_like_filter(SubscriptionTable.note),
        "statuses": status_filter,
        "tags": tags_filter,
        "tag": tags_filter,
        "tsv": tsv_filter,
        "startDate": generic_is_like_filter(SubscriptionTable.start_date),
        "endDate": generic_is_like_filter(SubscriptionTable.end_date),
    }
    | start_date_range_filters
    | end_date_range_filters
)

subscription_filter_fields = list(SUBSCRIPTION_FILTER_FUNCTIONS_BY_COLUMN.keys())
filter_subscriptions = generic_filter(SUBSCRIPTION_FILTER_FUNCTIONS_BY_COLUMN)

filter_by_query_string = add_subscription_search_query_filter
