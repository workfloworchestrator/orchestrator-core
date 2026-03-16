# Copyright 2019-2025 SURF, GÉANT.
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


from dataclasses import dataclass

from ag_ui.core import CustomEvent
from pydantic import Field
from typing_extensions import TypedDict

from orchestrator.search.agent.state import SearchState
from orchestrator.search.agent.utils import current_timestamp_ms


class AgentStepActiveValue(TypedDict, total=False):
    """Typed structure for AGENT_STEP_ACTIVE event value."""

    step: str
    reasoning: str


class AgentStepActiveEvent(CustomEvent):
    """Event emitted when an agent step becomes active."""

    name: str = Field(default="AGENT_STEP_ACTIVE", frozen=True)
    value: AgentStepActiveValue


def make_step_active_event(step_name: str, reasoning: str | None = None) -> AgentStepActiveEvent:
    """Create an AGENT_STEP_ACTIVE event for yielding into the event stream."""
    value = AgentStepActiveValue(step=step_name)
    if reasoning:
        value["reasoning"] = reasoning
    return AgentStepActiveEvent(timestamp=current_timestamp_ms(), value=value)


class PlanCreatedTaskValue(TypedDict):
    """Single task in a PLAN_CREATED event."""

    skill_name: str
    reasoning: str


class PlanCreatedEvent(CustomEvent):
    """Event emitted after the planner creates an execution plan."""

    name: str = Field(default="PLAN_CREATED", frozen=True)
    value: list[PlanCreatedTaskValue]


def make_plan_created_event(tasks: list[PlanCreatedTaskValue]) -> PlanCreatedEvent:
    """Create a PLAN_CREATED event for yielding into the event stream."""
    return PlanCreatedEvent(timestamp=current_timestamp_ms(), value=tasks)


@dataclass
class RunContext:
    """Execution context passed to Planner and SkillRunner."""

    state: SearchState
