from typing import Literal
from uuid import UUID

import structlog
from more_itertools import one, unique_everseen
from strawberry.dataloader import DataLoader

from orchestrator.db import (
    SubscriptionTable,
)
from orchestrator.services.subscription_relations import get_depends_on_subscriptions, get_in_use_by_subscriptions
from orchestrator.types import SubscriptionLifecycle

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


SubsLoaderType = DataLoader[tuple[UUID, tuple[str, ...]], list[SubscriptionTable]]
