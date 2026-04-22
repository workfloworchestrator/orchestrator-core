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

import pytest
from orchestrator.core.forms import FormValidationError
from orchestrator.core.types import SubscriptionLifecycle

from products.product_types.example1 import Example1
from test.unit_tests.workflows import assert_complete, extract_state, run_workflow


@pytest.mark.workflow
def test_happy_flow(responses, example1_subscription):
    # when

    # TODO: insert mocks here if needed

    result, _, _ = run_workflow("terminate_example1", [{"subscription_id": example1_subscription}, {}])

    # then

    assert_complete(result)
    state = extract_state(result)
    assert "subscription" in state

    # Check subscription in DB

    example1 = Example1.from_subscription(example1_subscription)
    assert example1.end_date is not None
    assert example1.status == SubscriptionLifecycle.TERMINATED


@pytest.mark.workflow
def test_can_only_terminate_when_modifiable_boolean_is_true(responses, example1_subscription):
    # given

    # TODO: set test conditions or fixture so that "Add an model_validator that requires some condition(s)" triggers

    # when

    with pytest.raises(FormValidationError) as error:
        result, _, _ = run_workflow("terminate_example1", [{"subscription_id": example1_subscription}, {}])

    # then

    assert error.value.errors[0]["msg"] == "Add an model_validator that requires some condition(s)"
