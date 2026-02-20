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

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from orchestrator.search.agent.memory import Memory
from orchestrator.search.filters import FilterTree
from orchestrator.search.query.queries import Query


class TaskAction(str, Enum):
    """The action to perform for a task."""

    SEARCH = "search"
    AGGREGATION = "aggregation"
    RESULT_ACTIONS = "result_actions"
    TEXT_RESPONSE = "text_response"


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    """Executable task descriptor for routing to skills."""

    action_type: TaskAction = Field(
        description="Which skill to execute: SEARCH (find entities), AGGREGATION (count/calculate/group), RESULT_ACTIONS (export/download/detailed results), TEXT_RESPONSE (answer questions)"
    )
    reasoning: str = Field(
        description="Human-readable explanation of what will be done (e.g., 'I need to search for active subscriptions created in 2024')"
    )
    status: TaskStatus = Field(
        default=TaskStatus.PENDING, exclude=True, description="Task execution status (managed internally)"
    )


class ExecutionPlan(BaseModel):
    """Sequential execution plan — structured output from the Planner LLM."""

    tasks: list[Task] = Field(
        description='List of tasks to execute in order. Use multiple tasks for compound requests (e.g., "find X and export" needs 2 tasks).'
    )


class SearchState(BaseModel):
    """Agent state for search operations.

    Tracks the current search context and execution status.
    """

    user_input: str = ""  # Original user input text from current conversation turn
    run_id: UUID | None = None
    query_id: UUID | None = None  # ID of the last persisted query (set by run_search/run_aggregation)
    query: Query | None = None
    pending_filters: FilterTree | None = None
    memory: Memory = Field(default_factory=Memory)


    class Config:
        arbitrary_types_allowed = True
