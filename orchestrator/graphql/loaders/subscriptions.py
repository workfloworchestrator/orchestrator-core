from uuid import UUID

import structlog
from strawberry.dataloader import DataLoader

from orchestrator.db import (
    SubscriptionTable,
)
from orchestrator.services.subscription_relations import get_depends_on_subscriptions, get_in_use_by_subscriptions
from orchestrator.types import SubscriptionLifecycle

logger = structlog.get_logger(__name__)


async def in_use_by_subs_loader(keys: list[tuple[UUID, tuple[str, ...]]]) -> list[list[SubscriptionTable]]:
    """GraphQL dataloader to efficiently get the in_use_by SubscriptionTables for multiple subscription_ids."""
    subscription_ids = [key[0] for key in keys]
    filter_statuses: tuple[str, ...] = keys[0][1] or tuple(SubscriptionLifecycle.values())

    if len({key[1] for key in keys}) > 1:
        raise Exception("Only one inUseByFilter.statuses can be defined")

    return await get_in_use_by_subscriptions(subscription_ids, filter_statuses)


async def depends_on_subs_loader(keys: list[tuple[UUID, tuple[str, ...]]]) -> list[list[SubscriptionTable]]:
    """GraphQL dataloader to efficiently get the depends_on SubscriptionTables for multiple subscription_ids."""
    subscription_ids = [key[0] for key in keys]
    filter_statuses: tuple[str, ...] = keys[0][1] or tuple(SubscriptionLifecycle.values())

    if len({key[1] for key in keys}) > 1:
        raise Exception("Only one dependsOnFilter.statuses can be defined")

    return await get_depends_on_subscriptions(subscription_ids, filter_statuses)


SubsLoaderType = DataLoader[tuple[UUID, tuple[str, ...]], list[SubscriptionTable]]
