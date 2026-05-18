# Copyright 2019-2026 SURF, GÉANT.
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

from orchestrator.core.services.subscriptions import (
    get_subscriptions_on_product_table,
    get_subscriptions_on_product_table_in_sync,
)
from orchestrator.core.services.workflows import (
    get_subscription_validations,
    start_subscription_validations,
)
from orchestrator.core.settings import app_settings, get_authorizers
from orchestrator.core.targets import Target
from orchestrator.core.workflow import StepList, done, init, step, workflow
from orchestrator.core.workflows.predicates import no_uncompleted_instance

logger = structlog.get_logger(__name__)


task_semaphore = BoundedSemaphore(value=2)

authorizers = get_authorizers()


@step("Validate subscriptions")
def validate_subscriptions() -> None:
    if app_settings.VALIDATE_OUT_OF_SYNC_SUBSCRIPTIONS:
        # Automatically re-validate out-of-sync subscriptions. This is not recommended for production.
        subscriptions = get_subscriptions_on_product_table()
    else:
        subscriptions = get_subscriptions_on_product_table_in_sync()

    # Map all SubscriptionTable objects to SubscriptionValidations tuples
    validations = list(get_subscription_validations(subscriptions))

    # Not possible to use SubscriptionTable objects past this point, as the original DB session will be closed
    for info in validations:
        logger.info("Starting subscription validation workflows", info=info)
        start_subscription_validations(info=info)


@workflow(
    target=Target.SYSTEM,
    authorize_callback=authorizers.authorize_callback,
    retry_auth_callback=authorizers.retry_auth_callback,
    run_predicate=no_uncompleted_instance,
)
def task_validate_subscriptions() -> StepList:
    return init >> validate_subscriptions >> done
