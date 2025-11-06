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

from uuid import UUID

from pydantic import BaseModel

from orchestrator.search.core.types import ActionType
from orchestrator.search.query.queries import Query


class SearchState(BaseModel):
    """Agent state for search operations.

    Tracks the current search context and execution status.
    """

    run_id: UUID | None = None
    query_id: UUID | None = None
    action: ActionType | None = None
    query: Query | None = None
    results_count: int | None = None  # Number of results from last executed search/aggregation
