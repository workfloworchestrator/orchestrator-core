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

import structlog
from orchestrator.core.forms import FormPage
from orchestrator.core.forms.validators import DisplaySubscription
from orchestrator.core.workflow import StepList, begin, step
from orchestrator.core.workflows.utils import terminate_workflow
from pydantic import model_validator
from pydantic_forms.types import InputForm, State, UUIDstr

from products.product_types.example1 import Example1

logger = structlog.get_logger(__name__)


def terminate_initial_input_form_generator(subscription_id: UUIDstr, customer_id: UUIDstr) -> InputForm:
    temp_subscription_id = subscription_id

    class TerminateExample1Form(FormPage):
        subscription_id: DisplaySubscription = temp_subscription_id  # type: ignore

        @model_validator(mode="after")
        def can_only_terminate_when_modifiable_boolean_is_true(self) -> "TerminateExample1Form":
            if False:  # TODO implement validation
                raise ValueError("Add an model_validator that requires some condition(s)")
            return self

    return TerminateExample1Form


@step("Delete subscription from OSS/BSS")
def delete_subscription_from_oss_bss(subscription: Example1) -> State:
    # TODO: add actual call to OSS/BSS to delete subscription

    return {}


additional_steps = begin


@terminate_workflow(initial_input_form=terminate_initial_input_form_generator, additional_steps=additional_steps)
def terminate_example1() -> StepList:
    return (
        begin >> delete_subscription_from_oss_bss
        # TODO: fill in additional steps if needed
    )
