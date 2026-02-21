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

from typing import TYPE_CHECKING, Any, AsyncIterator, Sequence
from uuid import uuid4

import structlog
from pydantic_ai import Agent, AgentRunResult, ModelSettings
from pydantic_ai._agent_graph import GraphAgentState
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    UserContent,
    UserPromptPart,
)
from pydantic_ai.messages import (
    TextPart as AiTextPart,
)
from pydantic_ai.run import AgentRunResultEvent
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset

if TYPE_CHECKING:
    from pydantic_ai.models import KnownModelName, Model
else:
    KnownModelName = str
    Model = Any

from orchestrator.search.agent.events import RunContext
from orchestrator.search.agent.planner import Planner
from orchestrator.search.agent.skills import SKILLS, Skill
from orchestrator.search.agent.state import SearchState, TaskAction

logger = structlog.get_logger(__name__)


class AgentAdapter(Agent[StateDeps[SearchState], str]):
    """Overrides run_stream_events to execute plans and stream events.

    Custom AG-UI events (e.g. AGENT_STEP_ACTIVE) are yielded directly from the planner
    and skill runners into the event stream. ArtifactEventStream (in ag_ui.py) passes
    them through to the frontend — pydantic-ai's default handler would drop them.

    The model/toolsets are required by Agent's constructor but unused here;
    the agents in Planner and SkillRunner handle actual LLM calls.
    """

    def __init__(
        self,
        model: "Model | KnownModelName | str",  # type: ignore[valid-type]
        skills: dict[TaskAction, Skill],
        *,
        deps_type: type[StateDeps[SearchState]] = StateDeps[SearchState],
        model_settings: "ModelSettings | None" = None,
        toolsets: Sequence[AbstractToolset[Any]] | None = None,
        instructions: Any = None,
        debug: bool = False,
    ):
        super().__init__(
            model=model,
            deps_type=deps_type,
            model_settings=model_settings or ModelSettings(),
            toolsets=toolsets or [],
            instructions=instructions or [],
        )
        self.skills = skills
        self.model_name = model if isinstance(model, str) else str(model)
        self._persistence: Any | None = None
        self._a2a_target_action: TaskAction | None = None
        self.debug = debug

    async def _prepare_state(self, deps: StateDeps[SearchState]) -> SearchState:
        """Load persisted state (if any) and start a new turn."""
        initial_state = deps.state
        user_input = initial_state.user_input

        if self._persistence:
            loaded = await self._persistence.load_state()
            if loaded:
                logger.debug("AgentAdapter: Resuming from previous state", run_id=self._persistence.run_id)
                initial_state = loaded
                initial_state.user_input = user_input

        if not initial_state.memory.current_turn or initial_state.memory.current_turn.user_question != user_input:
            initial_state.memory.start_turn(user_input)

        return initial_state

    @staticmethod
    def _extract_user_input(
        user_prompt: str | Sequence[UserContent] | None,
        message_history: Sequence[ModelMessage] | None,
    ) -> str:
        """Extract user input text from user_prompt or message_history."""
        if user_prompt and isinstance(user_prompt, str):
            return user_prompt
        if message_history:
            for msg in reversed(message_history):
                if isinstance(msg, ModelRequest):
                    for part in msg.parts:
                        if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                            return part.content
        return ""

    async def run(  # type: ignore[override]
        self,
        user_prompt: str | Sequence[UserContent] | None = None,
        *,
        message_history: Sequence[ModelMessage] | None = None,
        deps: StateDeps[SearchState] | None = None,
        target_action: TaskAction | None = None,
        **kwargs: Any,
    ) -> AgentRunResult[str]:
        """Non-streaming execution for A2A.

        Wraps run_stream_events() — the same streaming pipeline — and
        collects tool results and the final output. This reuses the entire
        existing execution without any parallel code path.
        """
        target_action = target_action or getattr(self, "_a2a_target_action", None)
        user_input = self._extract_user_input(user_prompt, message_history)

        if deps is None:
            deps = StateDeps(SearchState())

        deps.state.user_input = user_input

        # Create AgentRunTable record for DB persistence (AG-UI endpoint does this)
        if not deps.state.run_id:
            from orchestrator.db import db
            from orchestrator.db.models import AgentRunTable

            deps.state.run_id = uuid4()
            agent_run = AgentRunTable(run_id=deps.state.run_id, thread_id=str(uuid4()), agent_type="a2a")
            db.session.add(agent_run)
            db.session.commit()

        logger.debug("AgentAdapter.run: Starting A2A execution (wrapping stream)")

        from pydantic_ai.messages import ToolReturnPart

        from orchestrator.search.agent.artifacts import ToolArtifact

        tool_results: list[str] = []
        final_output = ""

        async for event in self.run_stream_events(deps=deps, target_action=target_action):
            # Collect tool results that carry ToolArtifact metadata (same pattern as AG-UI adapter)
            if isinstance(event, FunctionToolResultEvent):
                result = event.result
                if isinstance(result, ToolReturnPart) and isinstance(result.metadata, ToolArtifact):
                    tool_results.append(str(result.content))

            # Capture the final result
            if isinstance(event, AgentRunResultEvent):
                final_output = str(event.result.output)

        # Combine: tool results are the data, final_output is the LLM summary
        if tool_results:
            combined = "\n\n".join(tool_results)
            if final_output and final_output != "Execution completed":
                combined = f"{final_output}\n\n{combined}"
            final_output = combined
        elif not final_output:
            final_output = "Execution completed"

        logger.debug("AgentAdapter.run: A2A execution complete", output_length=len(final_output))

        # Build message history so AgentWorker can convert it to A2A agent messages.
        # Without this, new_messages() returns [] and the A2A task history has no agent response.
        state = GraphAgentState(
            message_history=[
                ModelRequest(parts=[UserPromptPart(content=user_input)]),
                ModelResponse(parts=[AiTextPart(content=final_output)]),
            ]
        )
        return AgentRunResult(output=final_output, _state=state, _new_message_index=0)

    async def run_stream_events(  # type: ignore[override]
        self,
        user_prompt: str | Sequence[UserContent] | None = None,
        *,
        deps: StateDeps[SearchState] | None = None,
        target_action: TaskAction | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[AgentStreamEvent | AgentRunResultEvent[str] | Any]:
        """Execute the plan and stream events in real-time.

        Custom events (AGENT_STEP_ACTIVE) are yielded directly from the planner
        and skill runners, then passed through by ArtifactEventStream.handle_event().
        """
        if deps is None:
            deps = StateDeps(SearchState())

        try:
            initial_state = await self._prepare_state(deps)
            ctx = RunContext(state=initial_state)
            planner = Planner(model=self.model_name, skills=self.skills, debug=self.debug)

            async for event in planner.execute(ctx, target_action=target_action):
                yield event

            ctx.state.memory.complete_turn(assistant_answer="Complete")
            deps.state = ctx.state

            if self._persistence:
                await self._persistence.snapshot(ctx.state)

            yield AgentRunResultEvent(result=AgentRunResult(output="Execution completed"))

        except Exception as e:
            logger.error("AgentAdapter: Execution failed", error=str(e), exc_info=True)
            raise


def build_agent_instance(
    model: str, agent_tools: list[FunctionToolset[Any]] | None = None, debug: bool = False
) -> AgentAdapter:
    """Build and configure the agent instance.

    Args:
        model: The LLM model to use
        agent_tools: Optional list of additional toolsets (currently unused)
        debug: Enable debug logging

    Returns:
        AgentAdapter instance
    """
    adapter = AgentAdapter(
        model=model,
        skills=SKILLS,
        deps_type=StateDeps[SearchState],
        debug=debug,
    )

    logger.debug("AgentAdapter: Built agent adapter", model=model)

    return adapter
