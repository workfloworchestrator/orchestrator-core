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
from typing import TypedDict
from uuid import UUID

from pydantic import BaseModel, Field

from orchestrator.search.agent.environment import ConversationEnvironment
from orchestrator.search.filters import FilterTree
from orchestrator.search.query.queries import Query


class TaskAction(str, Enum):
    """The action to perform for a task."""

    SEARCH = "search"
    AGGREGATION = "aggregation"
    RESULT_ACTIONS = "result_actions"
    TEXT_RESPONSE = "text_response"


class SkillMetadata(TypedDict):
    name: str
    description: str
    tags: list[str]


TASK_ACTION_SKILLS: dict[TaskAction, SkillMetadata] = {
    TaskAction.SEARCH: {
        "name": "Search",
        "description": "Find subscriptions, products, workflows, processes",
        "tags": ["search", "query"],
    },
    TaskAction.AGGREGATION: {
        "name": "Aggregate",
        "description": "Count, sum, avg with grouping",
        "tags": ["aggregate", "analytics"],
    },
    TaskAction.RESULT_ACTIONS: {
        "name": "Result Actions",
        "description": "Export results or fetch entity details",
        "tags": ["export", "details"],
    },
    TaskAction.TEXT_RESPONSE: {
        "name": "Text Response",
        "description": "Answer general questions about the system",
        "tags": ["text", "help"],
    },
}


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    """Executable task descriptor for routing to action nodes."""

    action_type: TaskAction = Field(
        description="Which action node to execute: SEARCH (find entities), AGGREGATION (count/calculate/group), RESULT_ACTIONS (get detailed data for a single entity OR prepare an export for a query), TEXT_RESPONSE (answer questions)"
    )
    reasoning: str = Field(
        description="Human-readable explanation of what will be done (e.g., 'I need to search for active subscriptions created in 2024')"
    )
    status: TaskStatus = Field(
        default=TaskStatus.PENDING, exclude=True, description="Task execution status (managed internally)"
    )

    @property
    def is_failed(self) -> bool:
        """Check if task has failed."""
        return self.status == TaskStatus.FAILED


class ExecutionPlan(BaseModel):
    """Sequential execution plan with task queue."""

    tasks: list[Task] = Field(
        description='List of tasks to execute in order. Use multiple tasks for compound requests (e.g., "find X and export" needs 2 tasks).'
    )
    current_index: int = Field(default=0, description="Index of current task being executed")

    @property
    def current(self) -> Task | None:
        """Get current task without advancing."""
        return self.tasks[self.current_index] if self.current_index < len(self.tasks) else None

    @property
    def is_complete(self) -> bool:
        """Check if all tasks are done."""
        return self.current_index >= len(self.tasks)

    @property
    def failed(self) -> bool:
        """Check if any task failed."""
        return any(task.is_failed for task in self.tasks)

    def next(self) -> None:
        """Advance to next task in the queue."""
        if not self.is_complete:
            self.current_index += 1


class SearchState(BaseModel):
    """Agent state for search operations.

    Tracks the current search context and execution status.
    """

    user_input: str = ""  # Original user input text from current conversation turn
    run_id: UUID | None = None
    query_id: UUID | None = None  # ID of the last persisted query (set by run_search/run_aggregation)
    query: Query | None = None
    pending_filters: FilterTree | None = None
    environment: ConversationEnvironment = Field(default_factory=ConversationEnvironment)

    execution_plan: ExecutionPlan | None = None  # Multi-step execution plan

    class Config:
        arbitrary_types_allowed = True
