# Copyright 2019-2025 SURF.
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

from uuid import UUID

from sqlalchemy import UUID as SA_UUID
from sqlalchemy import cast as sa_cast
from sqlalchemy import select
from sqlalchemy.orm import raiseload

from orchestrator.db import SubscriptionInstanceRelationTable, SubscriptionInstanceTable, db


def _eagerload_subscription_instances(
    subscription_id: UUID | str, instance_attributes: list[str]
) -> list[SubscriptionInstanceTable]:
    """Given a subscription id, recursively query all depends_on subscription instances with the instance_attributes eagerloaded.

    Note: accessing instance attributes on the result that were not explicitly loaded will
    trigger a sqlalchemy error.
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

    # Eagerload specified instance attributes
    query_loaders = get_query_loaders_for_model_paths(SubscriptionInstanceTable, instance_attributes)
    # Prevent unwanted lazyloading of all other attributes
    query_loaders += [raiseload("*")]  # type: ignore[list-item]  # todo fix this type
    stmt = (
        select(SubscriptionInstanceTable)
        .where(SubscriptionInstanceTable.subscription_instance_id.in_(select(select_all_instance_ids)))
        .options(*query_loaders)
    )

    return db.session.scalars(stmt).all()  # type: ignore[return-value]  # todo fix this type


def eagerload_all_subscription_instances(subscription_id: UUID | str) -> list[SubscriptionInstanceTable]:
    """Recursively find the subscription's depends_on instances and resolve relations for SubscriptionModel.from_subscription_id()."""
    instance_attributes = [
        "subscription.product",
        "product_block",
        "values.resource_type",
        "depends_on",
        "in_use_by",
    ]
    return _eagerload_subscription_instances(subscription_id, instance_attributes)


def eagerload_all_subscription_instances_only_inuseby(subscription_id: UUID | str) -> list[SubscriptionInstanceTable]:
    """Recursively find the subscription's depends_on instances and resolve their in_use_by relations."""
    instance_attributes = [
        "in_use_by",
    ]
    return _eagerload_subscription_instances(subscription_id, instance_attributes)
