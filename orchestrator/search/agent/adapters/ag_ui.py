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

"""AG-UI adapter — orchestration and custom transport layer.

AGUIWorker owns the full AG-UI request lifecycle (state setup, persistence,
streaming) so the HTTP endpoint stays a thin request/response handler.

AGUIEventStream / _AGUIAdapter customise the pydantic-ai transport:
1. Replace full tool results with lightweight ToolArtifact references
2. Pass through CustomEvent instances (e.g. AGENT_STEP_ACTIVE) that
   pydantic-ai's default handle_event() would silently drop
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ag_ui.core import BaseEvent, CustomEvent, EventType, RunAgentInput, ToolCallResultEvent
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.messages import FunctionToolResultEvent, ToolReturnPart
from pydantic_ai.ui import NativeEvent
from pydantic_ai.ui.ag_ui import AGUIAdapter
from pydantic_ai.ui.ag_ui import AGUIEventStream as _BaseAGUIEventStream
from sqlalchemy.orm import Session
from structlog import get_logger

from orchestrator.db.models import AgentRunTable
from orchestrator.search.agent.artifacts import ToolArtifact
from orchestrator.search.agent.persistence import PostgresStatePersistence
from orchestrator.search.agent.state import SearchState

if __name__ != "__main__":
    from orchestrator.search.agent.agent import AgentAdapter

logger = get_logger(__name__)


@dataclass
class AGUIEventStream(_BaseAGUIEventStream[Any, Any]):
    """Custom event stream for the search agent.

    - Replaces tool results that carry ToolArtifact metadata with the artifact JSON,
      so the AG-UI frontend receives a lightweight reference instead of full data.
    - Yields CustomEvent instances (AGENT_STEP_ACTIVE) that the base class would drop.
    """

    async def handle_event(self, event: NativeEvent) -> AsyncIterator[BaseEvent]:
        # Pass through AG-UI CustomEvents (e.g. AGENT_STEP_ACTIVE) that the
        # base class match/case would silently discard.
        if isinstance(event, CustomEvent):
            yield event
            return

        async for e in super().handle_event(event):
            yield e

    async def handle_function_tool_result(self, event: FunctionToolResultEvent) -> AsyncIterator[BaseEvent]:
        result = event.result
        if isinstance(result, ToolReturnPart) and isinstance(result.metadata, ToolArtifact):
            yield ToolCallResultEvent(
                message_id=self.new_message_id(),
                type=EventType.TOOL_CALL_RESULT,
                role="tool",
                tool_call_id=result.tool_call_id,
                content=result.metadata.model_dump_json(),
            )
            return

        # Default behavior for all other tools
        async for e in super().handle_function_tool_result(event):
            yield e


class _AGUIAdapter(AGUIAdapter[Any, Any]):
    """AGUIAdapter that uses AGUIEventStream."""

    def build_event_stream(self) -> AGUIEventStream:
        return AGUIEventStream(self.run_input, accept=self.accept)


class AGUIWorker:
    """Orchestrates AG-UI request handling: state setup, persistence, stream creation.

    Parallel to A2AWorker — owns the full AG-UI lifecycle so the HTTP endpoint
    stays a thin request/response handler.
    """

    @staticmethod
    async def run_request(
        agent: AgentAdapter,
        run_input: RunAgentInput,
        db_session: Session,
    ) -> AsyncIterator[str]:
        """Execute the full AG-UI lifecycle and return an SSE event iterator.

        Steps:
        1. Extract user input from messages and inject into state
        2. Create/fetch an AgentRunTable record
        3. Set up persistence and load previous state if available
        4. Create the _AGUIAdapter, run the stream, and yield SSE events
        5. Commit on success, rollback on failure
        """
        prepared = AGUIWorker._prepare_run_input(run_input)

        run_id = UUID(prepared.run_id)
        thread_id = prepared.thread_id

        # Create or get agent run record
        agent_run = db_session.get(AgentRunTable, run_id)
        if not agent_run:
            agent_run = AgentRunTable(run_id=run_id, thread_id=thread_id, agent_type="search")
            db_session.add(agent_run)
            db_session.commit()
            logger.debug("Created new agent run", run_id=str(run_id), thread_id=thread_id)

        prepared.state["run_id"] = run_id

        persistence = PostgresStatePersistence(thread_id=thread_id, run_id=run_id, session=db_session)

        loaded_state = await persistence.load_state()
        if loaded_state:
            initial_state = loaded_state
            initial_state.user_input = prepared.state["user_input"]
            initial_state.run_id = run_id
            logger.debug(
                "Loaded previous state from persistence",
                completed_turns=len(initial_state.memory.completed_turns),
                current_turn=initial_state.memory.current_turn is not None,
            )
        else:
            initial_state = SearchState(**prepared.state)
            logger.debug("Created fresh state (no previous snapshot)")

        # Set persistence on agent instance
        agent._persistence = persistence

        # Create adapter — all event handling (artifacts, custom events) flows through the stream
        adapter = _AGUIAdapter(agent=agent, run_input=prepared)
        event_stream = adapter.encode_stream(adapter.run_stream(deps=StateDeps(initial_state)))

        async def _stream_with_persistence() -> AsyncIterator[str]:
            """Stream AG-UI events and commit DB on completion."""
            try:
                async for event_str in event_stream:
                    yield event_str
                db_session.commit()
            except Exception as e:
                logger.error("Error in agent stream", error=str(e), exc_info=True)
                db_session.rollback()
                raise

        return _stream_with_persistence()

    @staticmethod
    def _prepare_run_input(run_input: RunAgentInput) -> RunAgentInput:
        """Prepare RunAgentInput by extracting user message and adding it to state."""
        user_input = AGUIWorker._extract_user_input(run_input)

        logger.debug("Extracted latest user message", user_input=user_input[:100] if user_input else "(empty)")

        state_dict = dict(run_input.state) if run_input.state else {}
        state_dict["user_input"] = user_input

        return RunAgentInput(
            thread_id=run_input.thread_id,
            run_id=run_input.run_id,
            state=state_dict,
            messages=run_input.messages,
            tools=run_input.tools,
            context=run_input.context,
            forwarded_props=run_input.forwarded_props,
        )

    @staticmethod
    def _extract_user_input(run_input: RunAgentInput) -> str:
        """Extract the most recent user message from RunAgentInput messages."""
        for msg in reversed(run_input.messages):
            if msg.role == "user" and isinstance(msg.content, str):
                return msg.content
        return ""
