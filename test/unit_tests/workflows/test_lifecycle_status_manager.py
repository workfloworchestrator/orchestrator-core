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
from unittest.mock import patch

from orchestrator.types import SubscriptionLifecycle
from orchestrator.workflow import StepList, begin, step
from orchestrator.workflows.utils import ensure_provisioning_status

@step("Dummy Step Success")
def dummy_step_success(state: dict) -> dict:
    """A dummy step that always succeeds."""
    state["dummy_step"] = "success"
    return {"status": "success"}

def mock_set_status(lifecycle: SubscriptionLifecycle):
    """Mock implementation of set_status to update the state."""
    @step(f"Set status to {lifecycle.name}")
    def _mock_step(state: dict):
        state["status"] = lifecycle  # Directly update the state without database interaction
        return {"status": lifecycle.name}  # Return a mock result
    return _mock_step

@patch("orchestrator.workflows.utils.set_status", side_effect=mock_set_status)
def test_ensure_provisioning_status_with_decorator(mock_set_status):
    """Test ensure_provisioning_status with annotation."""
    @ensure_provisioning_status
    @step("Test Step Success")
    def test_step_success(state: dict) -> dict:
        state["test_step"] = "success"
        return {"status": "success"}

    # Build the workflow
    steps = (
        begin
        >> test_step_success
        >> dummy_step_success
    )
    assert isinstance(steps, StepList)
    assert steps[0].name == "Set status to PROVISIONING"  # Updated to match uppercase
    assert steps[1].name == "Test Step Success"
    assert steps[2].name == "Set status to ACTIVE"
    assert steps[3].name == "Dummy Step Success"

    # Simulate execution and check final status
    state = {"status": None}
    try:
        for step_func in steps:
            step_func(state)
    except ValueError as e:
        pass
    assert state["status"] == SubscriptionLifecycle.ACTIVE

