from uuid import UUID

from sqlalchemy import UUID as SA_UUID
from sqlalchemy import cast as sa_cast
from sqlalchemy import select

from orchestrator.db import SubscriptionInstanceRelationTable, SubscriptionInstanceTable, db
from pydantic_forms.types import UUIDstr


def eagerload_all_subscription_instances(subscription_id: UUID | UUIDstr) -> None:
    """Given a subscription id, recursively query all depends_on subscription instances with all relationships.

    This function was designed to use in SubscriptionModel.from_subscription() for reducing
    the number of lazyload queries that occurred from loading subscription instances.
    """
    from orchestrator.db.loaders import get_query_loaders_for_model_paths

    # CTE to recursively get all subscription instance ids the subscription depends on
    instance_ids_cte = (
        select(
            sa_cast(None, SA_UUID(as_uuid=True)).label("in_use_by_id"),
            SubscriptionInstanceTable.subscription_instance_id.label("depends_on_id"),
        )
        .where(SubscriptionInstanceTable.subscription_id == subscription_id)
        .cte(name="recursive_instance_ids", recursive=True)
    )

    cte_alias = instance_ids_cte.alias()
    rel_alias = select(SubscriptionInstanceRelationTable).alias()

    instance_ids = instance_ids_cte.union(
        select(rel_alias.c.in_use_by_id, rel_alias.c.depends_on_id).where(
            rel_alias.c.in_use_by_id == cte_alias.c.depends_on_id
        )
    )

    select_all_instance_ids = select(instance_ids.c.depends_on_id).subquery()

    # Relationship attributes accessed on subscription instances during DomainModel instantiation.
    # For these we set eagerloading options to avoid ad-hoc lazy loading, thereby keeping the number of queries
    # constant regardless of how many 'layers' of instances a subscription has.
    #
    # The disadvantage is that for subscriptions with a relatively small product type, the performance becomes
    # slightly worse as it performs more queries than the old SubscriptionModel._get_subscription method
    model_paths = [
        "subscription.product",
        "product_block",
        "values.resource_type",
        "depends_on",
        "in_use_by",
    ]

    query_loaders = get_query_loaders_for_model_paths(SubscriptionInstanceTable, model_paths)
    stmt = (
        select(SubscriptionInstanceTable)
        .where(SubscriptionInstanceTable.subscription_instance_id.in_(select(select_all_instance_ids)))
        .options(*query_loaders)
    )

    db.session.execute(stmt).all()
