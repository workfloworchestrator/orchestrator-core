# Copyright 2024-2026 SURF, GÉANT.
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
from orchestrator.core.types import SubscriptionLifecycle

from products.product_types.example4 import Example4
from test.unit_tests.workflows import assert_complete, extract_state, run_workflow


@pytest.mark.workflow
def test_happy_flow(responses, example4_subscription):
    # when

    # TODO: insert mocks here if needed

    result, _, _ = run_workflow("terminate_example4", [{"subscription_id": example4_subscription}, {}])

    # then

    assert_complete(result)
    state = extract_state(result)
    assert "subscription" in state

    # Check subscription in DB

    example4 = Example4.from_subscription(example4_subscription)
    assert example4.end_date is not None
    assert example4.status == SubscriptionLifecycle.TERMINATED
