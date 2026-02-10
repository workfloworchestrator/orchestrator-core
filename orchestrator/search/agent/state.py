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
from orchestrator.search.core.types import QueryOperation
from orchestrator.search.query.queries import Query


class IntentType(str, Enum):
    """User's intent - determines which action node to route to."""

    SEARCH = "search"
    AGGREGATION = "aggregation"
    RESULT_ACTIONS = "result_actions"
    TEXT_RESPONSE = "text_response"
    NO_MORE_ACTIONS = "no_more_actions"


class SearchState(BaseModel):
    """Agent state for search operations.

    Tracks the current search context and execution status.
    """

    user_input: str = ""  # Original user input text from current conversation turn
    run_id: UUID | None = None
    query_id: UUID | None = None
    query_operation: QueryOperation | None = None  # Type of query operation (SELECT, COUNT, AGGREGATE)
    query: Query | None = None
    results_count: int | None = None  # Number of results from last executed search/aggregation
    intent: IntentType | None = None  # User's intent, determines routing
    export_url: str | None = None  # Export URL if export has been prepared
    end_actions: bool = False  # Whether to end after current action completes (set by IntentNode)
    environment: ConversationEnvironment = Field(default_factory=ConversationEnvironment)

    class Config:
        arbitrary_types_allowed = True
