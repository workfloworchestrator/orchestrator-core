# Copyright 2019-2024 SURF, GÉANT.
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
from functools import cache
from typing import Any

import structlog

from orchestrator.db import ProductTable
from orchestrator.forms import FormPage
from orchestrator.forms.validators import Choice
from orchestrator.services.subscriptions import (
    get_subscriptions_on_product_table_in_sync,
)
from orchestrator.services.workflows import (
    get_validation_product_workflows_for_subscription,
    start_validation_workflow_for_workflows,
)
from orchestrator.targets import Target
from orchestrator.workflow import StepList, done, init, step, workflow
from pydantic_forms.types import FormGenerator, State

logger = structlog.get_logger(__name__)


def create_select_product_type_form() -> type[FormPage]:
    """Get and create the choices form for the product type."""

    @cache
    def get_product_type_choices() -> dict[Any, Any]:
        return {product.product_type: product.product_type for product in ProductTable.query.all()}

    ProductTypeChoices = Choice.__call__("Product Type", get_product_type_choices())

    class SelectProductTypeForm(FormPage):
        product_type: ProductTypeChoices  # type: ignore

    return SelectProductTypeForm


def initial_input_form_generator() -> FormGenerator:
    """Generate the form."""

    init_input = yield create_select_product_type_form()
    user_input_data = init_input.model_dump()

    return user_input_data


@step("Validate Product Type")
def validate_product_type(product_type: str) -> State:
    result = []
    subscriptions = get_subscriptions_on_product_table_in_sync()

    for subscription in subscriptions:
        system_product_workflows = get_validation_product_workflows_for_subscription(
            subscription=subscription,
        )

        if not system_product_workflows:
            logger.warning(
                "SubscriptionTable has no validation workflow",
                subscription=subscription,
                product=subscription.product.name,
            )
            continue

        validation_result = start_validation_workflow_for_workflows(
            subscription=subscription,
            workflows=system_product_workflows,
            product_type_filter=product_type,
        )
        if len(validation_result) > 0:
            result.append({"total_workflows_validated": len(validation_result), "workflows": validation_result})

    return {"result": result}


@workflow(
    "Validate all subscriptions of Product Type", target=Target.SYSTEM, initial_input_form=initial_input_form_generator
)
def task_validate_product_type() -> StepList:
    return init >> validate_product_type >> done
