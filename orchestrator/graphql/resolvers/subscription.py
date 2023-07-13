# Copyright 2019-2020 SURF.
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

from typing import Union

import structlog

from orchestrator.db import ProductTable, SubscriptionTable
from orchestrator.db.filters import Filter
from orchestrator.db.filters.subscription import filter_subscriptions
from orchestrator.db.range import apply_range_to_query
from orchestrator.db.sorting import Sort, sort_subscriptions
from orchestrator.graphql.pagination import Connection, PageInfo
from orchestrator.graphql.schemas.subscription import SubscriptionType
from orchestrator.graphql.types import CustomInfo, GraphqlFilter, GraphqlSort
from orchestrator.graphql.utils.create_resolver_error_handler import create_resolver_error_handler

logger = structlog.get_logger(__name__)


async def resolve_subscriptions(
    info: CustomInfo,
    filter_by: Union[list[GraphqlFilter], None] = None,
    sort_by: Union[list[GraphqlSort], None] = None,
    first: int = 10,
    after: int = 0,
) -> Connection[SubscriptionType]:
    _error_handler = create_resolver_error_handler(info)

    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    logger.info("resolve_subscription() called", range=[after, after + first], sort=sort_by, filter=pydantic_filter_by)

    query = SubscriptionTable.query.join(ProductTable)

    query = filter_subscriptions(query, pydantic_filter_by, _error_handler)
    query = sort_subscriptions(query, pydantic_sort_by, _error_handler)
    total = query.count()
    query = apply_range_to_query(query, after, first)

    subscriptions = query.all()
    has_next_page = len(subscriptions) > first

    # exclude last item as it was fetched to know if there is a next page
    subscriptions = subscriptions[:first]
    subscriptions_length = len(subscriptions)
    start_cursor = after if subscriptions_length else None
    end_cursor = after + subscriptions_length - 1
    page_subscriptions = [SubscriptionType.from_pydantic(p) for p in subscriptions]

    return Connection(
        page=page_subscriptions,
        page_info=PageInfo(
            has_previous_page=bool(after),
            has_next_page=has_next_page,
            start_cursor=start_cursor,
            end_cursor=end_cursor,
            total_items=total if total else None,
        ),
    )
