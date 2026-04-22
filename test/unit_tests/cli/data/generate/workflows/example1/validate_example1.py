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
from orchestrator.core.workflow import StepList, begin, step
from orchestrator.core.workflows.utils import validate_workflow
from pydantic_forms.types import State

from products.product_types.example1 import Example1

logger = structlog.get_logger(__name__)


@step("Load initial state")
def load_initial_state_example1(subscription: Example1) -> State:
    return {
        "subscription": subscription,
    }


@step("Validate that the example1 subscription is correctly administered in some external system")
def check_validate_example_in_some_oss(subscription: Example1) -> State:
    # TODO: add validation for "Validate that the example1 subscription is correctly administered in some external system"
    if True:
        raise ValueError("Validate that the example1 subscription is correctly administered in some external system")

    return {}


@validate_workflow()
def validate_example1() -> StepList:
    return begin >> load_initial_state_example1 >> check_validate_example_in_some_oss
