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

import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncIterator, Sequence, cast

import structlog
from fasta2a.applications import FastA2A
from fasta2a.broker import InMemoryBroker
from fasta2a.schema import Message, Part, Skill, TaskSendParams
from fasta2a.schema import TextPart as A2ATextPart
from fasta2a.storage import InMemoryStorage
from pydantic_ai._a2a import AgentWorker
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.messages import (
    FunctionToolResultEvent,
    ModelRequest,
    ModelResponse,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.messages import (
    TextPart as AiTextPart,
)
from pydantic_ai.run import AgentRunResultEvent

from orchestrator.search.agent.agent import AgentAdapter
from orchestrator.search.agent.artifacts import ToolArtifact
from orchestrator.search.agent.skills import SKILLS
from orchestrator.search.agent.state import SearchState, TaskAction

logger = structlog.get_logger(__name__)

A2A_SKILLS = [
    Skill(
        id=action.value,
        name=skill.name,
        description=skill.description,
        tags=skill.tags,
        input_modes=["application/json"],
        output_modes=["application/json"],
    )
    for action, skill in SKILLS.items()
]


class A2AWorker(AgentWorker):  # type: ignore[type-arg]
    """AgentWorker subclass that consumes the agent's event stream directly.

    Bypasses ``AgentWorker.run_task()`` (which calls ``agent.run()``) and
    instead drives ``agent.run_stream_events()`` — the same pipeline used by
    the AG-UI adapter.  This keeps ``AgentAdapter`` protocol-agnostic while
    giving the A2A adapter full control over stream consumption and result
    assembly.

    The A2A protocol advertises skills on the Agent Card but has no first-class
    field for targeting a skill on ``message/send``. The convention is to pass
    ``{"skill_id": "<action>"}`` in the message metadata.  This worker extracts
    that hint and passes it as ``target_action`` to skip the planner.
    """

    async def run_task(self, params: TaskSendParams) -> None:
        agent = cast(AgentAdapter, self.agent)

        task = await self.storage.load_task(params["id"])
        if task is None:
            raise ValueError(f'Task {params["id"]} not found')

        if task["status"]["state"] != "submitted":
            raise ValueError(f'Task {params["id"]} has already been processed (state: {task["status"]["state"]})')

        await self.storage.update_task(task["id"], state="working")

        metadata = params["message"].get("metadata", {}) or {}
        skill_id = metadata.get("skill_id") or metadata.get("skillId")
        target_action: TaskAction | None = None

        if skill_id:
            try:
                target_action = TaskAction(skill_id)
                logger.debug("A2A: Routing to skill directly", target_action=target_action)
            except ValueError:
                logger.warning("A2A: Unknown skillId, falling back to planner", skill_id=skill_id)

        user_input = self._extract_user_input(task.get("history", []))

        deps = StateDeps(SearchState(user_input=user_input))

        from orchestrator.db import db
        from orchestrator.db.models import AgentRunTable

        deps.state.run_id = uuid.uuid4()
        agent_run = AgentRunTable(run_id=deps.state.run_id, thread_id=str(uuid.uuid4()), agent_type="a2a")
        db.session.add(agent_run)
        db.session.commit()

        logger.debug("A2AWorker: Starting execution", task_id=task["id"])

        try:
            final_output = await self._consume_stream(agent, deps, target_action)

            a2a_messages: list[Message] = [
                Message(
                    role="agent",
                    parts=[A2ATextPart(kind="text", text=final_output)],
                    kind="message",
                    message_id=str(uuid.uuid4()),
                )
            ]

            # Update context with synthetic message history so multi-turn works
            context_messages = await self.storage.load_context(task["context_id"]) or []
            context_messages.extend([
                ModelRequest(parts=[UserPromptPart(content=user_input)]),
                ModelResponse(parts=[AiTextPart(content=final_output)]),
            ])
            await self.storage.update_context(task["context_id"], context_messages)

            artifacts = self.build_artifacts(final_output)
        except Exception:
            await self.storage.update_task(task["id"], state="failed")
            raise
        else:
            await self.storage.update_task(
                task["id"], state="completed", new_artifacts=artifacts, new_messages=a2a_messages
            )

    @staticmethod
    async def _consume_stream(
        agent: AgentAdapter,
        deps: StateDeps[SearchState],
        target_action: TaskAction | None,
    ) -> str:
        """Consume the agent event stream and collect the final output.

        Collects ToolArtifact results from tool calls and the final LLM output,
        combining them into a single response string.
        """
        tool_results: list[str] = []
        final_output = ""

        async for event in agent.run_stream_events(deps=deps, target_action=target_action):
            if isinstance(event, FunctionToolResultEvent):
                result = event.result
                if isinstance(result, ToolReturnPart) and isinstance(result.metadata, ToolArtifact):
                    tool_results.append(str(result.content))

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

        logger.debug("A2AWorker: Execution complete", output_length=len(final_output))
        return final_output

    @staticmethod
    def _extract_user_input(history: list[Message] | Sequence[Message]) -> str:
        """Extract user input text from A2A task history messages."""

        def _is_text_part(part: Part) -> bool:
            return part.get("kind") == "text"

        for msg in reversed(history):
            if msg.get("role") == "user":
                for part in msg.get("parts", []):
                    if _is_text_part(part):
                        return cast(A2ATextPart, part)["text"]
        return ""


def create_a2a_app(agent: AgentAdapter, url: str = "http://localhost:8080/api/a2a/") -> FastA2A:
    """Create an A2A (Agent-to-Agent) app from the search agent.

    Builds the FastA2A app, broker, storage, and worker manually (instead of
    using ``agent_to_a2a``) so that the worker lifecycle can be tied to the
    host application's lifespan when mounted as a sub-app.

    Args:
        agent: The AgentAdapter instance to expose via A2A.
        url: The public URL where the A2A endpoint is accessible.

    Returns:
        A FastA2A Starlette application to be mounted in the main app.
        The ``_a2a_worker`` and ``_a2a_agent`` attributes are set on the app
        so that the host can start them in its own startup/shutdown hooks.
    """
    storage = InMemoryStorage()
    broker = InMemoryBroker()
    worker = A2AWorker(agent=agent, broker=broker, storage=storage)  # type: ignore[arg-type]

    @asynccontextmanager
    async def _noop_lifespan(app: FastA2A) -> AsyncIterator[None]:
        yield

    a2a_app = FastA2A(
        storage=storage,
        broker=broker,
        name="WFO Search Agent",
        url=url,
        description="Search, filter and aggregate orchestration data",
        skills=A2A_SKILLS,
        lifespan=_noop_lifespan,
    )

    # Expose internals so the host app can manage the lifecycle
    a2a_app._a2a_worker = worker  # type: ignore[attr-defined]
    a2a_app._a2a_agent = agent  # type: ignore[attr-defined]

    return a2a_app


async def start_a2a(a2a_app: FastA2A) -> AsyncExitStack:
    """Start the A2A task manager, agent, and worker.

    Call this during host application startup. Returns an AsyncExitStack
    that must be closed during shutdown to cleanly stop everything.
    """
    stack = AsyncExitStack()
    await stack.__aenter__()
    await stack.enter_async_context(a2a_app.task_manager)
    await stack.enter_async_context(a2a_app._a2a_agent)  # type: ignore[attr-defined]
    await stack.enter_async_context(a2a_app._a2a_worker.run())  # type: ignore[attr-defined]
    return stack
