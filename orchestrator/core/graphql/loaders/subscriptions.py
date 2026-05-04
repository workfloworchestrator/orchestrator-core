# Copyright 2019-2026 SURF, GÉANT.
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

from datetime import datetime
from typing import Literal
from uuid import UUID

import structlog
from more_itertools import one, unique_everseen
from strawberry.dataloader import DataLoader

from orchestrator.core.db import (
    SubscriptionTable,
)
from orchestrator.core.services.subscription_relations import (
    get_depends_on_subscriptions,
    get_in_use_by_subscriptions,
    get_last_validation_datetimes,
)
from orchestrator.core.types import SubscriptionLifecycle

logger = structlog.get_logger(__name__)


def unzip_subscription_ids_and_filter_statuses(
    keys: list[tuple[UUID, tuple[str, ...]]], direction: Literal["dependsOn", "inUseBy"]
) -> tuple[list[UUID], tuple[str, ...]]:
    subscription_ids = [key[0] for key in keys]
    filter_statuses_values = (key[1] for key in keys)
    filter_statuses = one(
        unique_everseen(filter_statuses_values),
        too_long=Exception(f"{direction}Filter.statuses must be set to the same value"),
    )
    return subscription_ids, tuple(filter_statuses or SubscriptionLifecycle.values())


async def in_use_by_subs_loader(keys: list[tuple[UUID, tuple[str, ...]]]) -> list[list[SubscriptionTable]]:
    """GraphQL dataloader to efficiently get the in_use_by SubscriptionTables for multiple subscription_ids."""
    subscription_ids, filter_statuses = unzip_subscription_ids_and_filter_statuses(keys, "inUseBy")
    return await get_in_use_by_subscriptions(subscription_ids, filter_statuses)


async def depends_on_subs_loader(keys: list[tuple[UUID, tuple[str, ...]]]) -> list[list[SubscriptionTable]]:
    """GraphQL dataloader to efficiently get the depends_on SubscriptionTables for multiple subscription_ids."""
    subscription_ids, filter_statuses = unzip_subscription_ids_and_filter_statuses(keys, "inUseBy")
    return await get_depends_on_subscriptions(subscription_ids, filter_statuses)


async def last_validation_datetime_loader(keys: list[UUID]) -> list[datetime | None]:
    """GraphQL dataloader to efficiently get the last validation datetime for multiple subscription_ids."""
    return await get_last_validation_datetimes(keys)


SubsLoaderType = DataLoader[tuple[UUID, tuple[str, ...]], list[SubscriptionTable]]
LastValidationLoaderType = DataLoader[UUID, datetime | None]
