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

from typing import Callable, Union

import structlog
from more_itertools import flatten, one
from pydantic.utils import to_lower_camel
from strawberry.types.nodes import InlineFragment, SelectedField, Selection

from orchestrator.db import ProductTable, SubscriptionTable
from orchestrator.db.filters import Filter
from orchestrator.db.filters.subscription import filter_subscriptions
from orchestrator.db.range import apply_range_to_query
from orchestrator.db.sorting import Sort, sort_subscriptions
from orchestrator.domain.base import SubscriptionModel
from orchestrator.graphql.pagination import Connection, PageInfo
from orchestrator.graphql.schemas.subscription import SubscriptionInterface, UnknownSubscription
from orchestrator.graphql.types import CustomInfo, GraphqlFilter, GraphqlSort
from orchestrator.graphql.utils.create_resolver_error_handler import create_resolver_error_handler
from orchestrator.types import SubscriptionLifecycle

logger = structlog.get_logger(__name__)
# Note: we can make this more fancy by adding metadata to the field annotation that indicates if a resolver
# needs subscription details or not, and use that information here. Left as an exercise for the reader.
resolvers_that_dont_need_details = ["in_use_by_subscriptions", "depends_on_subscriptions", "processes"]
base_sub_props = (
    [
        to_lower_camel(key)
        for key in SubscriptionInterface.__annotations__
        if not isinstance(getattr(SubscriptionInterface, key, None), Callable)  # type: ignore
    ]
    + ["__typename"]
    + resolvers_that_dont_need_details
)


def _has_subscription_details(info: CustomInfo) -> bool:
    """Check if the query asks for subscription details (surf specific properties)."""

    def get_selections(selected_field: Selection) -> list[Selection]:
        def has_field_name(selection: Selection, field_name: str) -> bool:
            return isinstance(selection, SelectedField) and selection.name == field_name

        page_field = [selection for selection in selected_field.selections if has_field_name(selection, "page")]

        if not page_field:
            return selected_field.selections
        return one(page_field).selections if page_field else []

    def has_details(selection: Selection) -> bool:
        match selection:
            case SelectedField():
                return selection.name not in base_sub_props
            case InlineFragment() as fragment:
                return any(has_details(selection) for selection in fragment.selections)
            case _:
                return True

    fields = flatten(get_selections(field) for field in info.selected_fields)
    return any(has_details(selection) for selection in fields if selection)


def get_subscription_details(subscription: SubscriptionTable) -> SubscriptionInterface:
    from orchestrator.graphql.schema import GRAPHQL_MODELS

    subscription_model = SubscriptionModel.from_subscription(subscription.subscription_id)
    subscription_model = subscription_model.from_other_lifecycle(subscription_model, SubscriptionLifecycle.TERMINATED)
    strawberry_type = GRAPHQL_MODELS[subscription_model.__base_type__.__name__]  # type: ignore
    return strawberry_type.from_pydantic(subscription_model)


async def resolve_subscriptions(
    info: CustomInfo,
    filter_by: Union[list[GraphqlFilter], None] = None,
    sort_by: Union[list[GraphqlSort], None] = None,
    first: int = 10,
    after: int = 0,
) -> Connection[SubscriptionInterface]:
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

    if _has_subscription_details(info):
        page_subscriptions = [get_subscription_details(p) for p in subscriptions]
    else:
        page_subscriptions = [UnknownSubscription.from_pydantic(p) for p in subscriptions]

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
