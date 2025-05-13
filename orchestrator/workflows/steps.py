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
from copy import deepcopy

import structlog
from pydantic import ValidationError

from orchestrator.db import db
from orchestrator.db.models import ProcessSubscriptionTable
from orchestrator.domain.base import SubscriptionModel
from orchestrator.services.settings import reset_search_index
from orchestrator.services.subscriptions import get_subscription
from orchestrator.targets import Target
from orchestrator.types import SubscriptionLifecycle
from orchestrator.utils.json import to_serializable
from orchestrator.workflow import Step, step
from pydantic_forms.types import State, UUIDstr

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


@step("Refresh subscription search index")
def refresh_subscription_search_index() -> State:
    try:
        reset_search_index()
    except Exception:
        # Don't fail workflow in case of unexpected error
        logger.warning("Error updated the subscriptions search index")
    return {}
