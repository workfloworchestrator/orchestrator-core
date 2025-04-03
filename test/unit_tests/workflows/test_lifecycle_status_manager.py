# Copyright 2019-2025 GÉANT, SURF, ESnet
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

from orchestrator.utils.state import inject_args
from orchestrator.workflow import StepList, begin, step
from orchestrator.workflows.utils import ensure_provisioning_status


@step("Dummy Step Success")
def dummy_step_success(state: dict) -> dict:
    """A dummy step that always succeeds."""
    state["dummy_step"] = "success"
    return {"status": "success"}


# Step definition: A test step that always succeeds, wrapped with ensure_provisioning_status
@ensure_provisioning_status
@step("Test Step Success")
def test_step_success(state: dict) -> dict:
    """A test step that always succeeds."""
    state["test_step"] = "success"
    return {"status": "success"}


# Pytest fixture to provide a mock state for testing
@pytest.fixture
def state(generic_subscription_1):
    """Fixture to provide a mock state with a generic subscription."""
    return {"subscription": generic_subscription_1}


# Test case: Ensure provisioning status is correctly applied in the workflow
@inject_args
def test_ensure_provisioning_status_with_decorator(state: dict):
    """Test ensure_provisioning_status with annotation."""
    # Build the workflow with steps
    steps = begin >> test_step_success >> dummy_step_success

    # Verify the workflow structure and sequence of the steps taken
    assert isinstance(steps, StepList)
    assert steps[0].name == "Set subscription to 'provisioning'"
    assert steps[1].name == "Test Step Success"
    assert steps[2].name == "Set subscription to 'active'"
    assert steps[3].name == "Dummy Step Success"

    # Simulate execution of the workflow
    for step_func in steps:
        step_func(state)

    # Assert final state values after workflow execution
    assert state["test_step"] == "success"  # Ensure test step succeeded
    assert state["dummy_step"] == "success"  # Ensure dummy step succeeded
