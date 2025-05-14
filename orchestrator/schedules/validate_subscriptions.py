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


from threading import BoundedSemaphore

import structlog

from orchestrator.schedules.scheduling import scheduler
from orchestrator.services.subscriptions import (
    get_subscriptions_on_product_table,
    get_subscriptions_on_product_table_in_sync,
)
from orchestrator.services.workflows import (
    get_validation_product_workflows_for_subscription,
    start_validation_workflow_for_workflows,
)
from orchestrator.settings import app_settings

logger = structlog.get_logger(__name__)


task_semaphore = BoundedSemaphore(value=2)


@scheduler(name="Subscriptions Validator", time_unit="day", at="00:10")
def validate_subscriptions() -> None:
    if app_settings.VALIDATE_OUT_OF_SYNC_SUBSCRIPTIONS:
        # Automatically re-validate out-of-sync subscriptions. This is not recommended for production.
        subscriptions = get_subscriptions_on_product_table()
    else:
        subscriptions = get_subscriptions_on_product_table_in_sync()

    for subscription in subscriptions:
        validation_product_workflows = get_validation_product_workflows_for_subscription(subscription)

        if not validation_product_workflows:
            logger.warning(
                "SubscriptionTable has no validation workflow",
                subscription=subscription,
                product=subscription.product.name,
            )
            break

        start_validation_workflow_for_workflows(subscription=subscription, workflows=validation_product_workflows)
