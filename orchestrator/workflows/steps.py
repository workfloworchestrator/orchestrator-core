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
from typing import Optional

import structlog

from orchestrator.db import db
from orchestrator.db.models import ProcessSubscriptionTable
from orchestrator.domain.base import SubscriptionModel
from orchestrator.targets import Target
from orchestrator.types import State, SubscriptionLifecycle, UUIDstr
from orchestrator.workflow import Step, step

logger = structlog.get_logger(__name__)


@step("Unlock subscription")
def resync(subscription: SubscriptionModel) -> State:
    """Transition a subscription to in sync."""
    subscription.insync = True
    return {"subscription": subscription}


@step("Lock subscription")
def unsync(subscription_id: UUIDstr, __old_subscription__: Optional[dict] = None) -> State:
    """
    Transition a subscription to out of sync.

    This step will also create a backup of the current subscription details in the state with the key
    `__old_subscription__`

    Note: Some workflows already change subscription details in the initial form step. This is not a best practice but
    it can be handy/needed for some scenarios. To ensure that you get a correct backup these forms need to create
    the backup in the initial form step and save it to `__old_subscription__`. This step will NOT overwrite any existing
    data in the state for the `__old_subscription__` key.
    """
    subscription = SubscriptionModel.from_subscription(subscription_id)

    # Handle backup if needed
    if __old_subscription__:
        logger.info(
            "Skipping backup of subscription details because it already exists in the state",
            subscription_id=str(subscription_id),
        )
        subscription_backup = __old_subscription__
    else:
        logger.info("Creating backup of subscription details in the state", subscription_id=str(subscription_id))
        subscription_backup = deepcopy(subscription.dict())

    # Handle transition
    if not subscription.insync:
        raise ValueError("Subscription is already out of sync, cannot continue!")
    subscription.insync = False

    return {"subscription": subscription, "__old_subscription__": subscription_backup}


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
        pid=process_id, subscription_id=subscription_id, workflow_target=workflow_target
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
