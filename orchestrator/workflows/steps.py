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
from copy import deepcopy
from typing import Any
from uuid import UUID

import structlog
from pydantic import ValidationError

from orchestrator.db import db
from orchestrator.db.models import ProcessSubscriptionTable
from orchestrator.domain.base import ProductBlockModel, SubscriptionModel
from orchestrator.services.settings import reset_search_index
from orchestrator.services.subscriptions import build_extended_domain_model, get_subscription
from orchestrator.targets import Target
from orchestrator.types import State, SubscriptionLifecycle, UUIDstr
from orchestrator.utils.json import to_serializable
from orchestrator.utils.redis import delete_from_redis, to_redis
from orchestrator.websocket import sync_invalidate_subscription_cache
from orchestrator.workflow import Step, step

logger = structlog.get_logger(__name__)


@step("Unlock subscription")
def resync(subscription: SubscriptionModel) -> State:
    """Transition a subscription to in sync."""
    subscription.insync = True
    return {"subscription": subscription}


@step("Lock subscription")
def unsync(subscription_id: UUIDstr, __old_subscriptions__: dict | None = None) -> State:
    """Transition a subscription to out of sync.

    This step will also create a backup of the current subscription details in the state with the key
    `__old_subscriptions__`

    Note:  This step will NOT overwrite any existing data in the state for the `__old_subscriptions__` key. Some
    workflows already change subscription details in the initial form step. This is not a best practice but
    it can be handy/needed for some scenarios. To ensure that you get a correct backup these forms need to create
    the backup in the initial form step and save it to `__old_subscriptions__`.

    An example, showing the creation of a backup for 2 subscriptions during the initial form step :

    ```
    subscription = YOUR_DOMAIN_MODEL.from_subscription(subscription_id)
    subscription_backup = {}
    subscription_backup[subscription.subscription_id] = deepcopy(subscription.model_dump())
    subscription_backup[second_subscription.subscription_id] = deepcopy(second_subscription.model_dump())
    return {..., "__old_subscriptions__": subscription_backup }
    ```

    It's also possible to make the backup for a subscription that doesn't have a domain model:

    ```
    from orchestrator.utils.json import to_serializable
    subscription = subscriptions.get_subscription(subscription_id)
    subscription_backup = {subscription_id: to_serializable(subscription)}
    Do your changes here ...
    return {..., "subscription": to_serializable(subscription), "__old_subscriptions__": subscription_backup }
    ```

    """
    try:
        subscription = SubscriptionModel.from_subscription(subscription_id)
    except ValidationError:
        subscription = get_subscription(subscription_id)  # type: ignore

    # Handle backup if needed
    if __old_subscriptions__ and __old_subscriptions__.get(subscription_id):
        logger.info(
            "Skipping backup of subscription details because it already exists in the state",
            subscription_id=str(subscription_id),
        )
        subscription_backup = __old_subscriptions__
    else:
        logger.info("Creating backup of subscription details in the state", subscription_id=str(subscription_id))
        subscription_backup = __old_subscriptions__ or {}
        if isinstance(subscription, SubscriptionModel):
            subscription_backup[str(subscription_id)] = deepcopy(subscription.model_dump())
        else:
            subscription_backup[str(subscription_id)] = to_serializable(subscription)  # type: ignore

    # Handle transition
    if not subscription.insync:
        raise ValueError("Subscription is already out of sync, cannot continue!")
    subscription.insync = False

    return {"subscription": subscription, "__old_subscriptions__": subscription_backup}


@step("Lock subscription")
def unsync_unchecked(subscription_id: UUIDstr) -> State:
    """Use for validation workflows that need to run if the subscription is out of sync."""
    subscription = SubscriptionModel.from_subscription(subscription_id)
    subscription.insync = False
    return {"subscription": subscription}


def store_process_subscription_relationship(
    process_id: UUIDstr, subscription_id: UUIDstr, workflow_target: str
) -> ProcessSubscriptionTable:
    process_subscription = ProcessSubscriptionTable(
        process_id=process_id, subscription_id=subscription_id, workflow_target=workflow_target
    )
    db.session.add(process_subscription)
    return process_subscription


def store_process_subscription(workflow_target: Target) -> Step:
    @step("Create Process Subscription relation")
    def _store_process_subscription(process_id: UUIDstr, subscription_id: UUIDstr) -> None:
        store_process_subscription_relationship(process_id, subscription_id, workflow_target)

    return _store_process_subscription


def set_status(status: SubscriptionLifecycle) -> Step:
    @step(f"Set subscription to '{status}'")
    def _set_status(subscription: SubscriptionModel) -> State:
        """Set subscription to status."""
        subscription = SubscriptionModel.from_other_lifecycle(subscription, status)
        return {"subscription": subscription}

    _set_status.__doc__ = f"Set subscription to '{status}'."
    return _set_status


@step("Remove domain model from cache")
def remove_domain_model_from_cache(
    workflow_name: str, subscription: SubscriptionModel | None = None, subscription_id: UUID | None = None
) -> State:
    """Remove the domain model from the cache if it exists.

    Args:
        workflow_name: The workflow name
        subscription: Subscription Model
        subscription_id: The subscription id

    Returns:
        State

    """

    if not (subscription or subscription_id):
        logger.warning("No subscription found in this workflow", workflow_name=workflow_name)
        return {"deleted_subscription_id": None}
    if subscription:
        delete_from_redis(subscription.subscription_id)
    elif subscription_id:
        delete_from_redis(subscription_id)

    return {"deleted_subscription_id": subscription_id or subscription.subscription_id}  # type: ignore[union-attr]


@step("Cache Subscription and related subscriptions")
def cache_domain_models(workflow_name: str, subscription: SubscriptionModel | None = None) -> State:  # noqa: C901
    """Attempt to cache all Subscriptions once they have been touched once.

    Args:
        workflow_name: The Workflow Name
        subscription:  The Subscription if it exists.

    Returns:
        Returns State.

    """
    cached_subscription_ids: set[UUID] = set()
    if not subscription:
        logger.warning("No subscription found in this workflow", workflow_name=workflow_name)
        return {"cached_subscription_ids": cached_subscription_ids}

    def _cache_other_subscriptions(product_block: ProductBlockModel) -> None:
        for field in product_block.model_fields:
            # subscription_instance is a ProductBlockModel or an arbitrary type
            subscription_instance: ProductBlockModel | Any = getattr(product_block, field)
            # If subscription_instance is a list, we need to step into it and loop.
            if isinstance(subscription_instance, list):
                for item in subscription_instance:
                    if isinstance(item, ProductBlockModel):
                        _cache_other_subscriptions(item)

            # If subscription_instance is a ProductBlockModel check the owner_subscription_id to decide the cache
            elif isinstance(subscription_instance, ProductBlockModel):
                _cache_other_subscriptions(subscription_instance)
                if not subscription_instance.owner_subscription_id == subscription.subscription_id:
                    cached_subscription_ids.add(subscription_instance.owner_subscription_id)

    for field in subscription.model_fields:
        # There always is a single Root Product Block, it cannot be a list, so no need to check.
        instance: ProductBlockModel | Any = getattr(subscription, field)
        if isinstance(instance, ProductBlockModel):
            _cache_other_subscriptions(instance)

    # Cache all the sub subscriptions
    for subscription_id in cached_subscription_ids:
        subscription_model = SubscriptionModel.from_subscription(subscription_id)
        to_redis(build_extended_domain_model(subscription_model))
        sync_invalidate_subscription_cache(subscription.subscription_id, invalidate_all=False)

    # Cache the main subscription
    to_redis(build_extended_domain_model(subscription))
    cached_subscription_ids.add(subscription.subscription_id)
    sync_invalidate_subscription_cache(subscription.subscription_id)

    return {"cached_subscription_ids": cached_subscription_ids}


@step("Refresh subscription search index")
def refresh_subscription_search_index() -> State:
    try:
        reset_search_index()
    except Exception:
        # Don't fail workflow in case of unexpected error
        logger.warning("Error updated the subscriptions search index")
    return {}
