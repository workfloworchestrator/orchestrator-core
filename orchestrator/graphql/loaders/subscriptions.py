from itertools import chain
from typing import Any, NamedTuple
from uuid import UUID

import structlog
from sqlalchemy import Row, select
from sqlalchemy import Text as SaText
from sqlalchemy import cast as sa_cast
from sqlalchemy.orm import aliased
from strawberry.dataloader import DataLoader

from orchestrator.db import (
    ResourceTypeTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    SubscriptionTable,
    db,
)
from orchestrator.db.models import (
    SubscriptionInstanceRelationTable,
)
from orchestrator.services.subscriptions import RELATION_RESOURCE_TYPES
from orchestrator.types import SubscriptionLifecycle

logger = structlog.get_logger(__name__)


class Relation(NamedTuple):
    depends_on_sub_id: UUID
    in_use_by_sub_id: UUID


def _get_instance_relations(instance_relations_query: Any) -> list[Relation]:
    def to_relation(row: Row[Any]) -> Relation:
        return Relation(row[0], row[1])

    return [to_relation(row) for row in db.session.execute(instance_relations_query)]


async def _get_in_use_by_instance_relations(subscription_ids: list[UUID], filter_statuses: list[str]) -> list[Relation]:
    """Get in_use_by by relations through subscription instance hierarchy."""
    in_use_by_subscriptions = aliased(SubscriptionTable)
    in_use_by_instances = aliased(SubscriptionInstanceTable)
    depends_on_instances = aliased(SubscriptionInstanceTable)

    query_get_in_use_by_ids = (
        select(depends_on_instances.subscription_id, in_use_by_instances.subscription_id)
        .distinct()
        .join(in_use_by_instances.subscription)
        .join(in_use_by_instances.depends_on_block_relations)
        .join(depends_on_instances, SubscriptionInstanceRelationTable.depends_on)
        .join(in_use_by_subscriptions, depends_on_instances.subscription)
        .filter(depends_on_instances.subscription_id.in_(set(subscription_ids)))
        .filter(in_use_by_instances.subscription_id != depends_on_instances.subscription_id)
        .filter(in_use_by_subscriptions.status.in_(filter_statuses))
    )

    return _get_instance_relations(query_get_in_use_by_ids)


async def _get_depends_on_instance_relations(
    subscription_ids: list[UUID], filter_statuses: list[str]
) -> list[Relation]:
    """Get depends_on relations through subscription instance hierarchy."""
    in_use_by_instances = aliased(SubscriptionInstanceTable)
    depends_on_instances = aliased(SubscriptionInstanceTable)
    depends_on_subscriptions = aliased(SubscriptionTable)

    query_get_depends_on_ids = (
        select(depends_on_instances.subscription_id, in_use_by_instances.subscription_id)
        .distinct()
        .join(depends_on_instances.subscription)
        .join(depends_on_instances.in_use_by_block_relations)
        .join(in_use_by_instances, SubscriptionInstanceRelationTable.in_use_by)
        .join(depends_on_subscriptions, in_use_by_instances.subscription)
        .filter(in_use_by_instances.subscription_id.in_(set(subscription_ids)))
        .filter(depends_on_instances.subscription_id != in_use_by_instances.subscription_id)
        .filter(depends_on_subscriptions.status.in_(filter_statuses))
    )

    return _get_instance_relations(query_get_depends_on_ids)


def _get_resource_type_relations(resource_type_relations_query: Any) -> list[Relation]:
    def to_relation(row: Row[Any]) -> Relation:
        return Relation(UUID(row[0]), row[1])

    return [to_relation(row) for row in db.session.execute(resource_type_relations_query)]


async def _get_in_use_by_resource_type_relations(
    subscription_ids: list[UUID], filter_statuses: list[str]
) -> list[Relation]:
    """Get in_use_by relations through resource types."""
    logger.warning("Using legacy RELATION_RESOURCE_TYPES to find in_use_by subs")

    in_use_by_subscriptions = aliased(SubscriptionTable)
    depends_on_instance_values = aliased(SubscriptionInstanceValueTable)

    # Convert UUIDs to string
    unique_subscription_ids = set(map(str, subscription_ids))

    query_get_in_use_by_ids = (
        select(depends_on_instance_values.value, in_use_by_subscriptions.subscription_id)
        .select_from(depends_on_instance_values)
        .join(SubscriptionInstanceTable)
        .join(in_use_by_subscriptions)
        .join(ResourceTypeTable)
        .filter(ResourceTypeTable.resource_type.in_(RELATION_RESOURCE_TYPES))
        .filter(depends_on_instance_values.value.in_(unique_subscription_ids))
        .filter(in_use_by_subscriptions.status.in_(filter_statuses))
    )

    return _get_resource_type_relations(query_get_in_use_by_ids)


async def _get_depends_on_resource_type_relations(
    subscription_ids: list[UUID], filter_statuses: list[str]
) -> list[Relation]:
    """Get depends_on relations through resource types."""
    logger.warning("Using legacy RELATION_RESOURCE_TYPES to find depends_on subs")

    depends_on_subscriptions = aliased(SubscriptionTable)
    in_use_by_instances = aliased(SubscriptionInstanceTable)
    in_use_by_instance_values = aliased(SubscriptionInstanceValueTable)

    unique_subscription_ids = set(subscription_ids)

    query_get_depends_on_ids = (
        select(in_use_by_instance_values.value, in_use_by_instances.subscription_id)
        .select_from(in_use_by_instance_values)
        .join(in_use_by_instances)
        .join(
            depends_on_subscriptions,
            in_use_by_instance_values.value == sa_cast(depends_on_subscriptions.subscription_id, SaText),
        )
        .join(ResourceTypeTable)
        .filter(ResourceTypeTable.resource_type.in_(RELATION_RESOURCE_TYPES))
        .filter(in_use_by_instances.subscription_id.in_(unique_subscription_ids))
        .filter(depends_on_subscriptions.status.in_(filter_statuses))
    )

    return _get_resource_type_relations(query_get_depends_on_ids)


async def _get_in_use_by_relations(subscription_ids: list[UUID], filter_statuses: list[str]) -> list[Relation]:
    if RELATION_RESOURCE_TYPES:
        # Find relations through resource types
        resource_type_relations = await _get_in_use_by_resource_type_relations(subscription_ids, filter_statuses)
    else:
        resource_type_relations = []
    # Find relations through instance hierarchy
    instance_relations = await _get_in_use_by_instance_relations(subscription_ids, filter_statuses)
    return list(chain(resource_type_relations, instance_relations))


async def _get_depends_on_relations(subscription_ids: list[UUID], filter_statuses: list[str]) -> list[Relation]:
    if RELATION_RESOURCE_TYPES:
        # Find relations through resource types
        resource_type_relations = await _get_depends_on_resource_type_relations(subscription_ids, filter_statuses)
    else:
        resource_type_relations = []
    # Find relations through instance hierarchy
    instance_relations = await _get_depends_on_instance_relations(subscription_ids, filter_statuses)
    return list(chain(resource_type_relations, instance_relations))


async def in_use_by_subs_loader(keys: list[tuple[UUID, list[str] | None]]) -> list[list[SubscriptionTable]]:
    """GraphQL dataloader to efficiently get the in_use_by SubscriptionTables for multiple subscription_ids."""
    subscription_ids = [key[0] for key in keys]
    filter_statuses: list[str] = keys[0][1] or SubscriptionLifecycle.values()

    in_use_by_relations = await _get_in_use_by_relations(subscription_ids, filter_statuses)

    # Retrieve SubscriptionTable for all unique inuseby ids
    unique_in_use_by_ids = {row.in_use_by_sub_id for row in in_use_by_relations}
    _in_use_by_subs = db.session.execute(
        select(SubscriptionTable).filter(SubscriptionTable.subscription_id.in_(unique_in_use_by_ids))
    ).scalars()
    in_use_by_subs = {subscription.subscription_id: subscription for subscription in _in_use_by_subs}

    # group (more_itertools.bucket doesn't seem to work for tuple of uuids)
    subscription_in_use_by_ids: dict[UUID, list[UUID]] = {}
    for relation in in_use_by_relations:
        subscription_in_use_by_ids.setdefault(relation.depends_on_sub_id, []).append(relation.in_use_by_sub_id)

    def get_in_use_by_subs(depends_on_id: UUID) -> list[SubscriptionTable]:
        in_use_by_ids = subscription_in_use_by_ids.get(depends_on_id, [])
        return [in_use_by_sub for id_ in in_use_by_ids if (in_use_by_sub := in_use_by_subs.get(id_))]

    # Important (as with any dataloader)
    # Return the list of inuseby subs in the exact same order as the ids passed to this function
    return [get_in_use_by_subs(subscription_id) for subscription_id in subscription_ids]


async def depends_on_subs_loader(keys: list[tuple[UUID, list[str] | None]]) -> list[list[SubscriptionTable]]:
    """GraphQL dataloader to efficiently get the depends_on SubscriptionTables for multiple subscription_ids."""
    subscription_ids = [key[0] for key in keys]
    filter_statuses: list[str] = keys[0][1] or SubscriptionLifecycle.values()

    depends_on_relations = await _get_depends_on_relations(subscription_ids, filter_statuses)

    # Retrieve SubscriptionTable for all unique dependson ids
    unique_depends_on_ids = {row.depends_on_sub_id for row in depends_on_relations}
    _depends_on_subs = db.session.execute(
        select(SubscriptionTable).filter(SubscriptionTable.subscription_id.in_(unique_depends_on_ids))
    ).scalars()
    depends_on_subs = {subscription.subscription_id: subscription for subscription in _depends_on_subs}

    # group (more_itertools.bucket doesn't seem to work for tuple of uuids)
    subscription_depends_on_ids: dict[UUID, list[UUID]] = {}
    for relation in depends_on_relations:
        subscription_depends_on_ids.setdefault(relation.in_use_by_sub_id, []).append(relation.depends_on_sub_id)

    def get_depends_on_subs(in_use_by_id: UUID) -> list[SubscriptionTable]:
        depends_on_ids = subscription_depends_on_ids.get(in_use_by_id, [])
        return [depends_on_sub for id_ in depends_on_ids if (depends_on_sub := depends_on_subs.get(id_))]

    # Important (as with any dataloader)
    # Return the list of dependson subs in the exact same order as the ids passed to this function
    return [get_depends_on_subs(subscription_id) for subscription_id in subscription_ids]


SubsLoaderType = DataLoader[tuple[UUID, list[str] | None], list[SubscriptionTable]]
