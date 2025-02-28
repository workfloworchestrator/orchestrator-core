from uuid import UUID

from sqlalchemy import distinct, literal, select

from orchestrator.db import (
    SubscriptionInstanceRelationTable,
    SubscriptionInstanceTable,
    db,
)
from pydantic_forms.types import UUIDstr


def get_all_subscription_instance_ids(subscription_id: UUID) -> list[UUID]:
    # TODO remove, just a proof of concept for the recursive cte
    instance_ids_cte = (
        select(
            literal(UUID("00000000-0000-0000-0000-000000000000")).label("in_use_by_id"),
            SubscriptionInstanceTable.subscription_instance_id.label("depends_on_id"),
        )
        .where(SubscriptionInstanceTable.subscription_id == subscription_id)
        .cte(recursive=True)
    )

    cte_alias = instance_ids_cte.alias()
    rel_alias = select(SubscriptionInstanceRelationTable).alias()

    instance_ids = instance_ids_cte.union_all(
        select(rel_alias.c.in_use_by_id, rel_alias.c.depends_on_id).where(
            rel_alias.c.in_use_by_id == cte_alias.c.depends_on_id
        )
    )

    statement = select(distinct(instance_ids.c.depends_on_id))

    return db.session.scalars(statement).all()  # type: ignore


def load_all_subscription_instances(subscription_id: UUID | UUIDstr) -> None:
    from orchestrator.db.path_loaders import get_query_loaders_for_query_paths

    # CTE to recursively get all subscription instance ids the subscription depends on
    instance_ids_cte = (
        select(
            literal(UUID("00000000-0000-0000-0000-000000000000")).label("in_use_by_id"),
            SubscriptionInstanceTable.subscription_instance_id.label("depends_on_id"),
        )
        .where(SubscriptionInstanceTable.subscription_id == subscription_id)
        .cte(name="recursive_instance_ids", recursive=True)
    )

    cte_alias = instance_ids_cte.alias()
    rel_alias = select(SubscriptionInstanceRelationTable).alias()

    instance_ids = instance_ids_cte.union_all(
        select(rel_alias.c.in_use_by_id, rel_alias.c.depends_on_id).where(
            rel_alias.c.in_use_by_id == cte_alias.c.depends_on_id
        )
    )

    select_all_instance_ids = select(distinct(instance_ids.c.depends_on_id)).subquery()

    # Relationship attributes accessed on subscription instances during DomainModel instantiation.
    # For these we set eagerloading options to avoid ad-hoc lazy loading, thereby keeping the number of queries
    # constant regardless of how many 'layers' of instances a subscription has.
    #
    # The disadvantage is that for subscriptions with a relatively small product type, the performance becomes
    # slightly worse as it performs more queries than the old SubscriptionModel._get_subscription method
    query_paths = [
        "subscription.product",
        "product_block",
        "values.resource_type",
        "depends_on",
        "in_use_by",
    ]

    query_loaders = get_query_loaders_for_query_paths(query_paths, SubscriptionInstanceTable)
    stmt = (
        select(SubscriptionInstanceTable)
        .where(SubscriptionInstanceTable.subscription_instance_id.in_(select(select_all_instance_ids)))
        .options(*query_loaders)
    )

    db.session.execute(stmt).all()
