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

from orchestrator.search.agent.environment import ConversationEnvironment
from orchestrator.search.core.types import EntityType, QueryOperation
from orchestrator.search.query.queries import Query


class IntentType(str, Enum):
    """User's intent - determines which action node to route to."""

    SEARCH = "search"
    AGGREGATION = "aggregation"
    RESULT_ACTIONS = "result_actions"
    TEXT_RESPONSE = "text_response"


class Task(BaseModel):
    """Executable task descriptor for routing to action nodes."""

    action_type: IntentType = Field(description="Which action node to execute")
    entity_type: EntityType | None = Field(default=None, description="Entity type for search/aggregation tasks")
    query_operation: QueryOperation | None = Field(
        default=None, description="Query operation type for search/aggregation tasks"
    )
    description: str = Field(description="Human-readable task description")
    status: str = Field(default="pending", description="Task status: pending, executing, completed, failed")
    error_message: str | None = Field(default=None, description="Error message if task failed")


class ExecutionPlan(BaseModel):
    """Sequential execution plan with task queue."""

    tasks: list[Task] = Field(description="List of tasks to execute in order")
    current_task_index: int = Field(default=0, description="Index of current task being executed")
    failed: bool = Field(default=False, description="Whether the plan has failed")

    def has_next_task(self) -> bool:
        """Check if there are more tasks to execute."""
        return self.current_task_index < len(self.tasks)

    def get_current_task(self) -> Task | None:
        """Get the current task to execute."""
        if self.has_next_task():
            return self.tasks[self.current_task_index]
        return None

    def complete_current_task(self) -> None:
        """Mark current task as completed and advance to next."""
        if self.has_next_task():
            self.tasks[self.current_task_index].status = "completed"
            self.current_task_index += 1

    def mark_current_failed(self, error: str) -> None:
        """Mark current task and plan as failed."""
        if self.has_next_task():
            self.tasks[self.current_task_index].status = "failed"
            self.tasks[self.current_task_index].error_message = error
        self.failed = True


class SearchState(BaseModel):
    """Agent state for search operations.

    Tracks the current search context and execution status.
    """

    user_input: str = ""  # Original user input text from current conversation turn
    run_id: UUID | None = None
    query: Query | None = None
    environment: ConversationEnvironment = Field(default_factory=ConversationEnvironment)

    execution_plan: ExecutionPlan | None = None  # Multi-step execution plan

    class Config:
        arbitrary_types_allowed = True
