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

from orchestrator.db import ProductTable, SubscriptionTable
from orchestrator.schedules.scheduling import scheduler
from orchestrator.services.processes import start_process
from orchestrator.services.subscriptions import TARGET_DEFAULT_USABLE_MAP, WF_USABLE_MAP
from orchestrator.targets import Target

logger = structlog.get_logger(__name__)


task_semaphore = BoundedSemaphore(value=2)


@scheduler(name="Subscriptions Validator", time_unit="day", at="00:10")
def validate_subscriptions() -> None:
    subscriptions = SubscriptionTable.query.join(ProductTable).filter(SubscriptionTable.insync.is_(True)).all()
    for subscription in subscriptions:
        validation_workflow = None

        for workflow in subscription.product.workflows:
            if workflow.target == Target.SYSTEM:
                validation_workflow = workflow.name

        if validation_workflow:
            default = TARGET_DEFAULT_USABLE_MAP[Target.SYSTEM]
            usable_when = WF_USABLE_MAP.get(validation_workflow, default)

            if subscription.status in usable_when:
                task_semaphore.acquire()
                json = [{"subscription_id": str(subscription.subscription_id)}]
                _, handle = start_process(validation_workflow, json)
                handle.add_done_callback(lambda _: task_semaphore.release())
        else:
            logger.warning(
                "SubscriptionTable has no validation workflow",
                subscription=subscription,
                product=subscription.product.name,
            )
