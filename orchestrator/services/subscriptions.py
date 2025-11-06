# Copyright 2019-2020 SURF, GÉANT.
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

"""Module that provides service functions on subscriptions."""

import pickle  # noqa: S403
from collections.abc import Sequence
from datetime import datetime
from hashlib import md5
from typing import Any, TypeVar, overload
from uuid import UUID

import more_itertools
import structlog
from more_itertools import first
from sqlalchemy import Text, cast, not_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Query, aliased, joinedload
from sqlalchemy.sql.expression import or_

from orchestrator.api.helpers import getattr_in, product_block_paths, update_in
from orchestrator.db import (
    ProductTable,
    ResourceTypeTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    SubscriptionTable,
    db,
)
from orchestrator.db.models import (
    SubscriptionCustomerDescriptionTable,
    SubscriptionInstanceRelationTable,
    SubscriptionMetadataTable,
)
from orchestrator.db.queries.subscription import (
    eagerload_all_subscription_instances_only_inuseby,
)
from orchestrator.domain.base import SubscriptionModel
from orchestrator.domain.context_cache import cache_subscription_models
from orchestrator.targets import Target
from orchestrator.types import SubscriptionLifecycle
from orchestrator.utils.datetime import nowtz
from orchestrator.utils.helpers import is_ipaddress_type
from pydantic_forms.types import UUIDstr

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=SubscriptionTable)


@overload
def get_subscription(subscription_id: UUID | UUIDstr, for_update: bool = False) -> SubscriptionTable: ...


@overload
def get_subscription(
    subscription_id: UUID | UUIDstr, for_update: bool = False, model: type[T] = SubscriptionTable
) -> T: ...


def get_subscription(
    subscription_id: UUID | UUIDstr, for_update: bool = False, model: type[T] = SubscriptionTable
) -> T:
    """Get the subscription.

    Args:
        subscription_id: The subscription_id
        for_update: specific whether we intend to update the subscription
        model: SubscriptionModelType

    Returns: A subscription object

    Raises: ValueError: if the requested Subscription does not exist in de database.

    """

    try:
        subscription = db.session.get(model, subscription_id, with_for_update=for_update)
    except SQLAlchemyError as e:
        raise ValueError("Invalid subscription id") from e

    if subscription:
        return subscription
    raise ValueError(f"Subscription with {subscription_id} does not exist in the database")


def get_subscription_metadata(subscription_id: UUIDstr) -> dict | None:
    subscription_metadata = SubscriptionMetadataTable.find_by_subscription_id(subscription_id)
    if subscription_metadata:
        return subscription_metadata.metadata_
    return None


def update_subscription_status(subscription_id: UUIDstr, status: str) -> SubscriptionTable:
    """Update the subscription status.

    Args:
        subscription_id: Id of the subscription to update.
        status: Status to transition to.

    Returns: Subscription

    """
    subscription = get_subscription(subscription_id, for_update=True)
    subscription.status = status
    return subscription


def update_subscription_description(subscription_id: UUIDstr, description: str) -> SubscriptionTable:
    """Update a subscription's description.

    Args:
        subscription_id: subscription id of the subscription to update
        description: new subscription description

    Returns: Subscription

    """
    subscription = get_subscription(subscription_id, for_update=True)
    subscription.description = description
    return subscription


def activate_subscription(subscription_id: UUIDstr) -> SubscriptionTable:
    """Activate subscription by subscription id.

    Args:
        subscription_id: subscription id of the subscription

    Returns: Subscription object

    """
    subscription = get_subscription(subscription_id, for_update=True)
    subscription.status = "active"
    subscription.start_date = nowtz()
    subscription.insync = True
    return subscription


def provision_subscription(subscription_id: UUIDstr) -> SubscriptionTable:
    """Provision subscription by subscription id.

    Args:
        subscription_id: Subscription id of the subscription

    Returns: Updated subscription object

    """
    subscription = get_subscription(subscription_id, for_update=True)
    subscription.status = "provisioning"
    subscription.insync = True
    return subscription


def migrate_subscription(subscription_id: UUIDstr) -> SubscriptionTable:
    """Migrate subscription by subscription id.

    Args:
        subscription_id: Subscription id of the subscription

    Returns: Updated subscription object

    """
    subscription = get_subscription(subscription_id, for_update=True)
    subscription.status = "migrating"
    subscription.insync = False
    return subscription


def unsync(subscription_id: UUIDstr, checked: bool = True) -> SubscriptionTable:
    """Unsync subscription by subscription id.

    Args:
        subscription_id: Subscription id of the subscription
        checked: Checked or not

    Returns: Updated subscription object

    """
    subscription = get_subscription(subscription_id, for_update=True)
    if checked and not subscription.insync:
        raise ValueError("Subscription is already out of sync, cannot continue!")
    subscription.insync = False
    return subscription


def resync(subscription_id: UUIDstr) -> SubscriptionTable:
    """Resync subscription by subscription id.

    Args:
        subscription_id: Subscription id of the subscription

    Returns: Updated subscription object

    """
    subscription = get_subscription(subscription_id, for_update=True)
    subscription.insync = True
    return subscription


def set_status_provisioning_subscription(subscription_id: UUIDstr) -> SubscriptionTable:
    return update_subscription_status(subscription_id, "provisioning")


def terminate_subscription(subscription_id: UUIDstr) -> SubscriptionTable:
    return update_subscription(subscription_id, status="terminated", end_date=nowtz())


def create_subscription(
    customer_id: str, product: ProductTable, subscription_name: str, subscription_id: UUIDstr
) -> UUID:
    subscription = SubscriptionTable(
        subscription_id=subscription_id,
        product_id=product.product_id,
        customer_id=customer_id,
        description=subscription_name,
        start_date=None,
        end_date=None,
        insync=False,
        status="initial",
    )
    db.session.add(subscription)

    return subscription.subscription_id


def update_subscription(subscription_id: str, **attrs: dict | UUIDstr | str | datetime) -> SubscriptionTable:
    """Update the subscription.

    Args:
        subscription_id: SubscriptionTable id of the subscription
        attrs: Attributes that will be set

    Returns: Subscription

    """

    subscription = get_subscription(subscription_id, for_update=True)

    for key, value in attrs.items():
        setattr(subscription, key, value)

    return subscription


def retrieve_node_subscriptions_by_name(node_name: str) -> list[SubscriptionTable]:
    stmt = (
        select(SubscriptionTable)
        .join(ProductTable)
        .join(SubscriptionInstanceTable)
        .join(SubscriptionInstanceValueTable)
        .join(ResourceTypeTable)
        .filter(SubscriptionInstanceValueTable.value == node_name)
        .filter(ResourceTypeTable.resource_type == "nso_device_id")
        .filter(SubscriptionTable.status.in_(["active", "provisioning"]))
    )
    return list(db.session.scalars(stmt))


def retrieve_subscription_by_subscription_instance_value(
    resource_type: str, value: str, sub_status: tuple = ("provisioning", "active")
) -> SubscriptionTable | None:
    """Retrieve a Subscriptions by resource_type and value.

    Args:
        resource_type: name of the resource type
        value: value of the resource type
        sub_status: status of the subscriptions

    Returns: Subscription or None

    """
    stmt = (
        select(SubscriptionTable)
        .join(SubscriptionInstanceTable)
        .join(SubscriptionInstanceValueTable)
        .join(ResourceTypeTable)
        .filter(SubscriptionInstanceValueTable.value == value)
        .filter(ResourceTypeTable.resource_type == resource_type)
        .filter(SubscriptionTable.status.in_(sub_status))
        .distinct(SubscriptionTable.subscription_id)
    )
    return db.session.scalars(stmt).one_or_none()


def query_in_use_by_subscriptions(subscription_id: UUID, filter_statuses: list[str] | None = None) -> Query:
    """Return a query with all subscriptions -in_use_by- that use this subscription with resource_type or direct relation.

    The query can be used to add extra filters when/where needed.
    """
    # Find relations through resource types
    resource_type_relations = (
        SubscriptionTable.query.join(SubscriptionInstanceTable)
        .options(joinedload(SubscriptionTable.customer_descriptions))
        .join(SubscriptionInstanceValueTable)
        .join(ResourceTypeTable)
        .filter(ResourceTypeTable.resource_type.in_(RELATION_RESOURCE_TYPES))
        .filter(SubscriptionInstanceValueTable.value == str(subscription_id))
        .with_entities(SubscriptionTable.subscription_id)
    )

    # Find relations through instance hierarchy
    in_use_by_instances = aliased(SubscriptionInstanceTable)
    depends_on_instances = aliased(SubscriptionInstanceTable)
    relation_relations = (
        SubscriptionTable.query.join(in_use_by_instances.subscription)
        .join(in_use_by_instances.depends_on_block_relations)
        .join(depends_on_instances, SubscriptionInstanceRelationTable.depends_on)
        .filter(depends_on_instances.subscription_id == subscription_id)
        .filter(in_use_by_instances.subscription_id != subscription_id)
        .with_entities(SubscriptionTable.subscription_id)
    )

    return SubscriptionTable.query.filter(
        or_(
            SubscriptionTable.subscription_id.in_(resource_type_relations.scalar_subquery()),
            SubscriptionTable.subscription_id.in_(relation_relations.scalar_subquery()),
        ),
        SubscriptionTable.status.in_(filter_statuses if filter_statuses else SubscriptionLifecycle.values()),
    )


def query_depends_on_subscriptions(subscription_id: UUID, filter_statuses: list[str] | None = None) -> Query:
    """Return a query with all subscriptions -depends_on- that this subscription is dependent on with resource_type or direct relation.

    The query can be used to add extra filters when/where needed.
    """
    # Find relations through resource types
    resource_type_relations = (
        SubscriptionInstanceTable.query.join(SubscriptionInstanceValueTable)
        .join(ResourceTypeTable)
        .filter(ResourceTypeTable.resource_type.in_(RELATION_RESOURCE_TYPES))
        .filter(SubscriptionInstanceTable.subscription_id == subscription_id)
        .join(SubscriptionTable, SubscriptionInstanceValueTable.value == cast(SubscriptionTable.subscription_id, Text))
        .with_entities(SubscriptionTable.subscription_id)
    )

    # Find relations through instance hierarchy
    in_use_by_instances = aliased(SubscriptionInstanceTable)
    depends_on_instances = aliased(SubscriptionInstanceTable)
    relation_relations = (
        SubscriptionTable.query.join(depends_on_instances.subscription)
        .join(depends_on_instances.in_use_by_block_relations)
        .join(in_use_by_instances, SubscriptionInstanceRelationTable.in_use_by)
        .filter(in_use_by_instances.subscription_id == subscription_id)
        .filter(depends_on_instances.subscription_id != subscription_id)
        .with_entities(SubscriptionTable.subscription_id)
    )

    return SubscriptionTable.query.filter(
        or_(
            SubscriptionTable.subscription_id.in_(resource_type_relations.scalar_subquery()),
            SubscriptionTable.subscription_id.in_(relation_relations.scalar_subquery()),
        ),
        SubscriptionTable.status.in_(filter_statuses if filter_statuses else SubscriptionLifecycle.values()),
    )


def _terminated_filter(query: Query) -> list[UUID]:
    return list(
        more_itertools.flatten(
            query.filter(SubscriptionTable.status != "terminated").with_entities(SubscriptionTable.subscription_id)
        )
    )


def _in_sync_filter(query: Query) -> list[UUID]:
    return list(
        more_itertools.flatten(
            query.filter(not_(SubscriptionTable.insync)).with_entities(SubscriptionTable.subscription_id)
        )
    )


RELATION_RESOURCE_TYPES: list[str] = []


def status_relations(subscription: SubscriptionTable | None) -> dict[str, list[UUID]]:
    """Return info about locked subscription dependencies.

    This call will be used by the client to determine if it's safe to
    start a MODIFY or TERMINATE workflow. There are 4 cases:

    1) The subscription is a IP, LightPath or ELAN: the depends_on subscriptions are checked for not 'insync' instances.
    2) The subscription is a ServicePort: in_use_by subscriptions are checked for not 'insync' instances and for in_use_by
       services that are not terminated.
    3) The subscription is a Node: Related Core link subscriptions are checked that there are no active instances
       This is only used for the terminate workflow and ignored for modify
    4) IP_prefix cannot be terminated when in use

    """
    if not subscription:
        return {"locked_relations": [], "unterminated_parents": [], "unterminated_in_use_by_subscriptions": []}
    in_use_by_query = query_in_use_by_subscriptions(subscription.subscription_id)

    unterminated_in_use_by_subscriptions = _terminated_filter(in_use_by_query)
    locked_in_use_by_block_relations = _in_sync_filter(in_use_by_query)

    depends_on_query = query_depends_on_subscriptions(subscription.subscription_id)

    locked_depends_on_block_relations = _in_sync_filter(depends_on_query)

    result = {
        "locked_relations": locked_in_use_by_block_relations + locked_depends_on_block_relations,
        "unterminated_parents": unterminated_in_use_by_subscriptions,
        "unterminated_in_use_by_subscriptions": unterminated_in_use_by_subscriptions,
    }

    logger.debug(
        "Returning status info for related subscriptions",
        result=result,
        subscription_id=str(subscription.subscription_id),
    )
    return result


def get_relations(subscription_id: UUIDstr) -> dict[str, list[UUID]]:
    subscription_table = db.session.get(
        SubscriptionTable,
        subscription_id,
        options=[
            joinedload(SubscriptionTable.product),
            joinedload(SubscriptionTable.product).joinedload(ProductTable.workflows),
        ],
    )
    return status_relations(subscription_table)


TARGET_DEFAULT_USABLE_MAP: dict[Target, list[str]] = {
    Target.CREATE: [],
    Target.MODIFY: ["active"],
    Target.TERMINATE: ["active", "provisioning"],
    Target.SYSTEM: ["active"],
    Target.VALIDATE: ["active"],
    Target.RECONCILE: ["active"],
}

WF_USABLE_MAP: dict[str, list[str]] = {}

WF_BLOCKED_BY_PARENTS: dict[str, bool] = {}
WF_BLOCKED_BY_IN_USE_BY_SUBSCRIPTIONS: dict[str, bool] = {}

WF_USABLE_WHILE_OUT_OF_SYNC: list[str] = ["modify_note"]


def subscription_workflows(subscription: SubscriptionTable) -> dict[str, Any]:
    """Return a dict containing all the workflows a user can start for this subscription.

    Args:
        subscription: an SqlAlchemy instance of a `db.SubscriptionTable`

    Returns:
        A dictionary with the following structure (reason and its related keys are only present when workflows are blocked):

        >>> {  # doctest:+SKIP
        ...     "reason": "Optional global reason like subscription is in use"
        ...     "create": [{"name": "workflow.name", "description": "workflow.description", "reason": "Optional reason why this specific workflow is blocked"}],
        ...     "modify": [],
        ...     "terminate": [],
        ...     "system": [],
        ...     "validate": [],
        ...     "reconcile: [],
        ... }

    """
    default_json: dict[str, Any] = {}

    if not subscription.insync:
        default_json["reason"] = "subscription.not_in_sync"
    else:
        data = status_relations(subscription)

        if data["locked_relations"]:
            default_json["reason"] = "subscription.relations_not_in_sync"
            default_json["locked_relations"] = data["locked_relations"]

    workflows: dict[str, Any] = {
        "create": [],
        "modify": [],
        "terminate": [],
        "system": [],
        "validate": [],
        "reconcile": [],
    }
    for workflow in subscription.product.workflows:
        if workflow.name in WF_USABLE_WHILE_OUT_OF_SYNC or workflow.is_task:
            # validations and modify note are also possible with: not in sync or locked relations
            workflow_json = {"name": workflow.name, "description": workflow.description}
        else:
            workflow_json = {"name": workflow.name, "description": workflow.description, **default_json}

        # Simple reasons like "not in sync" and "locked_relations" are handled now. Handle special lifecycle cases:
        if "reason" not in workflow_json:
            default = TARGET_DEFAULT_USABLE_MAP[workflow.target]
            usable_when = WF_USABLE_MAP.get(workflow.name, default)

            if subscription.status not in usable_when:
                workflow_json["reason"] = "subscription.no_modify_invalid_status"
                workflow_json["usable_when"] = usable_when
                workflow_json["status"] = subscription.status
                workflow_json["action"] = "terminated" if workflow.target == Target.TERMINATE else "modified"

            # Check if this workflow is blocked because there are unterminated relations
            blocked_by_depends_on_subscriptions = WF_BLOCKED_BY_IN_USE_BY_SUBSCRIPTIONS.get(
                workflow.name, workflow.target == Target.TERMINATE
            )

            if not blocked_by_depends_on_subscriptions:
                blocked_by_depends_on_subscriptions = WF_BLOCKED_BY_PARENTS.get(
                    workflow.name, workflow.target == Target.TERMINATE
                )
            if blocked_by_depends_on_subscriptions and data["unterminated_in_use_by_subscriptions"]:
                workflow_json["reason"] = "subscription.no_modify_subscription_in_use_by_others"
                workflow_json["unterminated_parents"] = data["unterminated_parents"]
                workflow_json["unterminated_in_use_by_subscriptions"] = data["unterminated_in_use_by_subscriptions"]
                workflow_json["action"] = "terminated" if workflow.target == Target.TERMINATE else "modified"

        workflows[workflow.target.lower()].append(workflow_json)

    return {**workflows, **default_json}


def _generate_etag(model: dict) -> str:
    encoded = pickle.dumps(model)
    return md5(encoded).hexdigest()  # noqa: S303, S324


def convert_to_in_use_by_relation(obj: Any) -> dict[str, str]:
    return {"subscription_instance_id": str(obj.subscription_instance_id), "subscription_id": str(obj.subscription_id)}


def build_domain_model(subscription_model: SubscriptionModel) -> dict:
    """Create a subscription dict from the SubscriptionModel."""
    with cache_subscription_models():
        return subscription_model.model_dump()


def build_extended_domain_model(subscription_model: SubscriptionModel) -> dict:
    """Create a subscription dict from the SubscriptionModel with additional keys."""

    stmt = select(SubscriptionCustomerDescriptionTable).where(
        SubscriptionCustomerDescriptionTable.subscription_id == subscription_model.subscription_id
    )
    customer_descriptions = list(db.session.scalars(stmt))

    with cache_subscription_models():
        subscription = subscription_model.model_dump()

    # query all subscription instances and inject the in_use_by_ids/in_use_by_relations into the subscription dict.
    instance_to_in_use_by = {
        instance.subscription_instance_id: instance.in_use_by
        for instance in eagerload_all_subscription_instances_only_inuseby(subscription_model.subscription_id)
    }
    inject_in_use_by_ids_v2(subscription, instance_to_in_use_by)

    subscription["customer_descriptions"] = customer_descriptions

    return subscription


def inject_in_use_by_ids_v2(dikt: dict, instance_to_in_use_by: dict[UUID, Sequence[SubscriptionInstanceTable]]) -> None:
    for value in dikt.values():
        if isinstance(value, dict):
            inject_in_use_by_ids_v2(value, instance_to_in_use_by)
        elif isinstance(value, list) and isinstance(first(value, None), dict):
            for item in value:
                inject_in_use_by_ids_v2(item, instance_to_in_use_by)

    if subscription_instance_id := dikt.get("subscription_instance_id"):
        in_use_by_subs = instance_to_in_use_by[subscription_instance_id]
        dikt["in_use_by_ids"] = [i.subscription_instance_id for i in in_use_by_subs]
        dikt["in_use_by_relations"] = [convert_to_in_use_by_relation(instance) for instance in in_use_by_subs]


def format_special_types(subscription: dict) -> dict:
    """Modifies the subscription dict in-place, formatting special types to string.

    This function was added during the Pydantic 2.x migration to handle serialization errors on ipaddress types.
    Background: https://github.com/pydantic/pydantic/issues/6669

    The problem lies with SubscriptionDomainModelSchema which allows extra untyped fields.
    It might be possible with a model_serializer but couldn't get this to work, therefore this workaround.
    """

    def format_value(v: Any) -> Any:
        if is_ipaddress_type(v):
            return str(v)
        if isinstance(v, dict):
            return format_special_types(v)
        if isinstance(v, list):
            return [format_value(item) for item in v]
        return v

    for k, v in subscription.items():
        subscription[k] = format_value(v)
    return subscription


def format_extended_domain_model(subscription: dict, filter_owner_relations: bool) -> dict:
    """Format the subscription dict depending on filter settings.

    Args:
        subscription: result from build_extended_domain_model() or cache
        filter_owner_relations: True to filter instance ids from the current subscription
    """

    def filter_instance_ids_on_subscription() -> None:
        paths = product_block_paths(subscription)
        instance_ids_to_filter = {getattr_in(subscription, f"{path}.subscription_instance_id") for path in paths}
        instance_ids_to_filter.add(subscription["subscription_id"])

        def filter_instance_ids_on_productblock(path_to_block: str) -> None:
            if not (block_instance_ids := getattr_in(subscription, f"{path_to_block}.in_use_by_ids")):
                return
            filtered_instance_ids = set(block_instance_ids) - instance_ids_to_filter
            update_in(subscription, f"{path_to_block}.in_use_by_ids", list(filtered_instance_ids))

        # find all product blocks, filter instance_ids if needed
        for path in paths:
            filter_instance_ids_on_productblock(path)

    if filter_owner_relations:
        filter_instance_ids_on_subscription()

    return subscription


def get_subscriptions_on_product_table() -> list[SubscriptionTable]:
    select_query = select(SubscriptionTable).join(ProductTable)
    return list(db.session.scalars(select_query))


def get_subscriptions_on_product_table_in_sync(in_sync: bool = True) -> list[SubscriptionTable]:
    select_query = select(SubscriptionTable).join(ProductTable).filter(SubscriptionTable.insync.is_(in_sync))
    return list(db.session.scalars(select_query))
