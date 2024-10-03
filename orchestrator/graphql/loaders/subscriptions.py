from uuid import UUID

import structlog
from strawberry.dataloader import DataLoader

from orchestrator.db import (
    SubscriptionTable,
)
from orchestrator.services.subscription_relations import get_depends_on_subscriptions, get_in_use_by_subscriptions
from orchestrator.types import SubscriptionLifecycle

logger = structlog.get_logger(__name__)


async def in_use_by_subs_loader(keys: list[tuple[UUID, str]]) -> list[list[SubscriptionTable]]:
    """GraphQL dataloader to efficiently get the in_use_by SubscriptionTables for multiple subscription_ids."""
    subscription_ids = [key[0] for key in keys]
    filter_statuses: list[str] = keys[0][1].split(",") or SubscriptionLifecycle.values()

    return await get_in_use_by_subscriptions(subscription_ids, filter_statuses)


async def depends_on_subs_loader(keys: list[tuple[UUID, str]]) -> list[list[SubscriptionTable]]:
    """GraphQL dataloader to efficiently get the depends_on SubscriptionTables for multiple subscription_ids."""
    subscription_ids = [key[0] for key in keys]
    filter_statuses: list[str] = keys[0][1].split(",") or SubscriptionLifecycle.values()

    return await get_depends_on_subscriptions(subscription_ids, filter_statuses)


SubsLoaderType = DataLoader[tuple[UUID, str], list[SubscriptionTable]]
