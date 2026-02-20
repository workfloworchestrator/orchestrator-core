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

from collections import deque
from typing import TYPE_CHECKING, Any, AsyncIterator, Sequence

import structlog
from pydantic_ai import Agent, AgentRunResult, ModelSettings
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.messages import (
    AgentStreamEvent,
    UserContent,
)
from pydantic_ai.run import AgentRunResultEvent
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset

if TYPE_CHECKING:
    from pydantic_ai.models import KnownModelName, Model
else:
    KnownModelName = str
    Model = Any

from orchestrator.search.agent.events import AgentDeps, RunContext
from orchestrator.search.agent.planner import Planner
from orchestrator.search.agent.skills import SKILLS, Skill
from orchestrator.search.agent.state import SearchState, TaskAction

logger = structlog.get_logger(__name__)


class AgentAdapter(Agent[StateDeps[SearchState], str]):
    """Overrides run_stream_events to inject custom AG-UI events.

    pydantic-ai's AG-UI pipeline filters out custom events via UIEventStream.handle_event().
    This adapter bypasses that by emitting AGENT_STEP_ACTIVE events through a deque that the
    endpoint reads between yielded events. The model/toolsets are required by Agent's constructor
    but unused, the agents in Planner and SkillRunner handle actual LLM calls.
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
        self.debug = debug

    def _emit_sse_event(self, event: Any) -> None:
        """Serialize an AG-UI event to SSE wire format and enqueue it."""
        self._current_events.append(f"data: {event.model_dump_json()}\n\n")

    async def _prepare_state(self, deps: StateDeps[SearchState]) -> tuple[SearchState, AgentDeps]:
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

        agent_deps = AgentDeps(_emit=self._emit_sse_event)
        return initial_state, agent_deps

    async def run_stream_events(  # type: ignore[override]
        self,
        user_prompt: str | Sequence[UserContent] | None = None,
        *,
        deps: StateDeps[SearchState] | None = None,
        target_action: TaskAction | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[AgentStreamEvent | AgentRunResultEvent[str] | Any]:
        """Execute the plan and stream events in real-time.

        This implementation manually streams events because pydantic-ai only supports
        emitting events from tool calls. Since we need to emit custom
        events (step transitions, state changes), we cannot use the standard AG-UI
        handlers (handle_ag_ui_request, AGUIAdapter.dispatch_request) as they filter
        out custom events via pattern matching in UIEventStream.handle_event().

        The pattern:
        1. Planner.execute() iterates the plan tasks
        2. Each task runs a SkillRunner that streams AgentStreamEvents
        3. Custom AGENT_STEP_ACTIVE events bypass via _current_events deque
        4. All events are yielded in real-time to the frontend
        """
        if deps is None:
            deps = StateDeps(SearchState())

        try:
            self._current_events: deque[str] = deque()
            initial_state, agent_deps = await self._prepare_state(deps)
            ctx = RunContext(state=initial_state, deps=agent_deps)
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
