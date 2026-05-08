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

from test.unit_tests.workflows import assert_complete, extract_state, run_workflow


@pytest.mark.workflow
def test_happy_flow(responses, example1_subscription):
    # when

    result, _, _ = run_workflow("validate_example1", {"subscription_id": example1_subscription})

    # then

    assert_complete(result)
    state = extract_state(result)
    assert state["check_core_db"] is True


@pytest.mark.workflow
def test_validate_example_in_some_oss(responses, example1_subscription):
    # given

    # TODO: set test conditions or fixture so that "Validate that the example1 subscription is correctly administered in some external system" triggers

    # when

    with pytest.raises(AssertionError) as error:
        result, _, _ = run_workflow("validate_example1", [{"subscription_id": example1_subscription}, {}])

    # then

    assert (
        error.value.errors[0]["msg"]
        == "Validate that the example1 subscription is correctly administered in some external system"
    )
