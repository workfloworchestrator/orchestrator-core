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

from functools import cache
from typing import Annotated, AsyncGenerator
from uuid import UUID

from ag_ui.core import RunAgentInput
from anyio import create_memory_object_stream, create_task_group
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from pydantic_ai.ag_ui import SSE_CONTENT_TYPE, StateDeps, run_ag_ui
from starlette.responses import Response, StreamingResponse
from structlog import get_logger

from orchestrator.db import db
from orchestrator.db.models import AgentRunTable
from orchestrator.search.agent.agent import AgentAdapter, build_agent_instance
from orchestrator.search.agent.persistence import PostgresStatePersistence
from orchestrator.search.agent.state import SearchState

router = APIRouter()
logger = get_logger(__name__)


def prepare_run_input(run_input: RunAgentInput) -> RunAgentInput:
    """Prepare RunAgentInput by extracting user message and adding it to state.

    This preprocessing is necessary because:
    - AG-UI transforms messages into LLM prompts during processing
    - We need the original user query text for tools and prompts
    - The endpoint is the only place with access to raw messages before transformation

    Args:
        run_input: Original RunAgentInput from the client

    Returns:
        Modified RunAgentInput with user_input added to state
    """
    # Extract the most recent user message
    user_input = ""
    for msg in reversed(run_input.messages):
        if msg.role == "user" and msg.content:
            user_input = msg.content
            break

    logger.debug("Extracted latest user message", user_input=user_input[:100] if user_input else "(empty)")

    # Build state dict for SearchState by extracting data from AG-UI messages
    # Preserve any existing state fields from client, then add our derived fields
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


@cache
def get_agent(request: Request) -> AgentAdapter:
    """Dependency to provide the agent instance.

    The agent is built once and cached for the lifetime of the application.
    """
    from orchestrator.llm_settings import llm_settings

    model = request.app.agent_model
    debug = llm_settings.AGENT_DEBUG

    logger.debug("Building agent instance", model=model, debug=debug)
    return build_agent_instance(model, debug=debug)


@router.post("/")
async def agent_conversation(
    request: Request,
    agent: Annotated[AgentAdapter, Depends(get_agent)],
) -> Response:
    """Agent conversation endpoint using pydantic-ai ag_ui protocol.

    This endpoint handles the interactive agent conversation for search.
    Uses manual stream management to allow custom events to be injected.
    """

    # Parse the request body to get RunAgentInput
    try:
        body = await request.json()
        run_input = RunAgentInput(**body)
    except ValidationError as e:
        logger.error("Invalid request body", error=str(e))
        raise HTTPException(status_code=400, detail=f"Invalid request body: {e}")

    # Prepare run_input with user message extracted into state
    prepared_run_input = prepare_run_input(run_input)

    # Create memory stream for events
    send_stream, receive_stream = create_memory_object_stream[str]()

    async def run_agent_task() -> None:
        """Run the agent and send events to the stream."""
        try:
            run_id = UUID(prepared_run_input.run_id)
            thread_id = prepared_run_input.thread_id

            # Create or get agent run record for persistence tracking
            agent_run = db.session.get(AgentRunTable, run_id)
            if not agent_run:
                agent_run = AgentRunTable(run_id=run_id, thread_id=thread_id, agent_type="search")
                db.session.add(agent_run)
                db.session.commit()
                logger.debug("Created new agent run", run_id=str(run_id), thread_id=thread_id)

            prepared_run_input.state["run_id"] = run_id

            persistence = PostgresStatePersistence(thread_id=thread_id, run_id=run_id, session=db.session)

            loaded_state = await persistence.load_state()
            if loaded_state:
                initial_state = loaded_state
                initial_state.user_input = prepared_run_input.state["user_input"]
                initial_state.run_id = run_id
                logger.debug(
                    "Loaded previous state from persistence",
                    completed_turns=len(initial_state.memory.completed_turns),
                    current_turn=initial_state.memory.current_turn is not None,
                )
            else:
                initial_state = SearchState(**prepared_run_input.state)
                logger.debug("Created fresh state (no previous snapshot)")

            # Set persistence on agent instance
            agent._persistence = persistence

            # Run agent with AG-UI protocol handling
            event_iterator = run_ag_ui(
                agent,
                run_input=prepared_run_input,
                deps=StateDeps(initial_state),
            )

            async for event_str in event_iterator:
                # First, check if there are any custom events to inject
                if hasattr(agent, "_current_events"):
                    while agent._current_events:
                        custom_event = agent._current_events.popleft()
                        await send_stream.send(custom_event)

                # Then send the AG-UI event
                await send_stream.send(event_str)

            # Commit transaction to persist snapshots
            db.session.commit()

        except Exception as e:
            logger.error("Error in run_agent_task", error=str(e), exc_info=True)
            db.session.rollback()
            raise
        finally:
            await send_stream.aclose()

    async def stream_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events from the memory stream."""
        async with create_task_group() as tg:
            # Start agent execution in background
            tg.start_soon(run_agent_task)

            # Stream events as they arrive
            async with receive_stream:
                async for event in receive_stream:
                    yield event

    return StreamingResponse(stream_generator(), media_type=SSE_CONTENT_TYPE)


