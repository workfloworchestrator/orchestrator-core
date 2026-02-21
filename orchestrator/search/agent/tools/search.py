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

from typing import cast

import structlog
from pydantic_ai import RunContext
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.messages import ToolReturn
from pydantic_ai.toolsets import FunctionToolset

from orchestrator.db import db
from orchestrator.search.agent.artifacts import QueryArtifact
from orchestrator.search.agent.handlers import execute_search_with_persistence
from orchestrator.search.agent.memory import ToolStep
from orchestrator.search.agent.state import SearchState
from orchestrator.search.agent.tools.filters import ensure_query_initialized
from orchestrator.search.core.types import EntityType
from orchestrator.search.query.queries import Query, SelectQuery
from orchestrator.search.query.results import QueryResultsResponse, ResultRow, VisualizationType

logger = structlog.get_logger(__name__)

search_execution_toolset: FunctionToolset[StateDeps[SearchState]] = FunctionToolset(max_retries=2)


@search_execution_toolset.tool
async def run_search(
    ctx: RunContext[StateDeps[SearchState]],
    entity_type: EntityType,
    limit: int = 10,
) -> ToolReturn:
    """Execute a search to find and rank entities.

    Use this tool for SELECT action to find entities matching your criteria.
    For counting or computing statistics, use run_aggregation instead.
    """
    ensure_query_initialized(ctx.deps.state, entity_type)
    query = cast(SelectQuery, cast(Query, ctx.deps.state.query).model_copy(update={"limit": limit}))

    search_response, run_id, query_id = await execute_search_with_persistence(query, db.session, ctx.deps.state.run_id)

    ctx.deps.state.run_id = run_id
    ctx.deps.state.query_id = query_id

    description = f"Searched {len(search_response.results)} {query.entity_type.value}"

    # Record tool step with query_id
    ctx.deps.state.memory.record_tool_step(
        ToolStep(
            step_type="run_search",
            description=description,
            context={"query_id": query_id, "query_snapshot": query.model_dump()},
        )
    )

    logger.debug(
        "Search completed",
        total_count=len(search_response.results),
        query_id=str(query_id),
    )

    # Build full response for LLM/A2A/MCP consumers
    result_rows = [
        ResultRow(
            group_values={"entity_id": r.entity_id, "title": r.entity_title, "entity_type": r.entity_type.value},
            aggregations={"score": r.score},
        )
        for r in search_response.results
    ]
    full_response = QueryResultsResponse(
        results=result_rows,
        total_results=len(result_rows),
        metadata=search_response.metadata,
        visualization_type=VisualizationType(type="table"),
    )

    # Lightweight artifact for AG-UI frontend (fetches full data via REST)
    artifact = QueryArtifact(
        query_id=str(query_id),
        total_results=len(result_rows),
        visualization_type=VisualizationType(type="table"),
        description=description,
    )

    return ToolReturn(return_value=full_response, metadata=artifact)
