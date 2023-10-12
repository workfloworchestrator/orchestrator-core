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
from pydantic.utils import to_lower_camel
from sqlalchemy import func, select

from orchestrator.db import ProductTable, SubscriptionTable, db
from orchestrator.db.filters import Filter
from orchestrator.db.filters.subscription import filter_subscriptions, subscription_filter_fields
from orchestrator.db.range import apply_range_to_statement
from orchestrator.db.sorting import Sort
from orchestrator.db.sorting.subscription import sort_subscriptions, subscription_sort_fields
from orchestrator.domain.base import SubscriptionModel
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.schemas.product import ProductModelGraphql
from orchestrator.graphql.schemas.subscription import Subscription, SubscriptionInterface
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils.create_resolver_error_handler import create_resolver_error_handler
from orchestrator.graphql.utils.is_query_detailed import is_query_detailed
from orchestrator.graphql.utils.to_graphql_result_page import to_graphql_result_page
from orchestrator.types import SubscriptionLifecycle

logger = structlog.get_logger(__name__)
# Note: we can make this more fancy by adding metadata to the field annotation that indicates if a resolver
# needs subscription details or not, and use that information here. Left as an exercise for the reader.
base_sub_props = tuple(
    [to_lower_camel(key) for key in SubscriptionInterface.__annotations__]
    + [to_lower_camel(key) for key in ProductModelGraphql.__annotations__]
    + ["__typename"]
)

_is_subscription_detailed = is_query_detailed(base_sub_props)


def get_subscription_details(subscription: SubscriptionTable) -> SubscriptionInterface:
    from orchestrator.graphql.autoregistration import graphql_subscription_name
    from orchestrator.graphql.schema import GRAPHQL_MODELS

    subscription_details = SubscriptionModel.from_subscription(subscription.subscription_id)
    base_model = subscription_details.__base_type__ if subscription_details.__base_type__ else subscription_details
    subscription_details = base_model.from_other_lifecycle(  # type: ignore
        subscription_details, SubscriptionLifecycle.INITIAL, skip_validation=True
    )
    strawberry_type = GRAPHQL_MODELS[graphql_subscription_name(base_model.__name__)]  # type: ignore
    return strawberry_type.from_pydantic(subscription_details)


async def resolve_subscriptions(
    info: OrchestratorInfo,
    filter_by: Union[list[GraphqlFilter], None] = None,
    sort_by: Union[list[GraphqlSort], None] = None,
    first: int = 10,
    after: int = 0,
) -> Connection[SubscriptionInterface]:
    _error_handler = create_resolver_error_handler(info)

    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []
    logger.debug("resolve_subscription() called", range=[after, after + first], sort=sort_by, filter=pydantic_filter_by)

    stmt = select(SubscriptionTable).join(ProductTable)

    stmt = filter_subscriptions(stmt, pydantic_filter_by, _error_handler)
    stmt = sort_subscriptions(stmt, pydantic_sort_by, _error_handler)
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = apply_range_to_statement(stmt, after, after + first + 1)

    subscriptions = db.session.scalars(stmt).all()

    if _is_subscription_detailed(info):
        graphql_subscriptions = [get_subscription_details(p) for p in subscriptions]
    else:
        graphql_subscriptions = [Subscription.from_pydantic(p) for p in subscriptions]
    return to_graphql_result_page(
        graphql_subscriptions, first, after, total, subscription_sort_fields, subscription_filter_fields
    )
