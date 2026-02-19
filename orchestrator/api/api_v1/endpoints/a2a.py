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

from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncIterator, cast

import structlog
from fasta2a.applications import FastA2A
from fasta2a.broker import InMemoryBroker
from fasta2a.schema import Skill, TaskSendParams
from fasta2a.storage import InMemoryStorage
from pydantic_ai._a2a import AgentWorker

from orchestrator.search.agent.agent import GraphAgentAdapter
from orchestrator.search.agent.skills import SKILLS
from orchestrator.search.agent.state import TaskAction

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


class SkillAwareWorker(AgentWorker):  # type: ignore[type-arg]
    """AgentWorker subclass that extracts skillId from A2A message metadata.

    The A2A protocol advertises skills on the Agent Card but has no first-class
    field for targeting a skill on ``message/send``. The convention is to pass
    ``{"skill_id": "<action>"}`` in the message metadata. This worker extracts
    that hint and sets it on the agent as ``_a2a_target_action`` before delegating
    to the parent ``run_task``. ``GraphAgentAdapter.run()`` picks it up and
    bypasses the planner, invoking the skill node directly (preventing 1 extra llm call).
    """

    async def run_task(self, params: TaskSendParams) -> None:
        agent = cast(GraphAgentAdapter, self.agent)
        metadata = params["message"].get("metadata", {})
        skill_id = metadata.get("skill_id") or metadata.get("skillId")

        if skill_id:
            try:
                agent._a2a_target_action = TaskAction(skill_id)
                logger.debug("A2A: Routing to skill directly", target_action=agent._a2a_target_action)
            except ValueError:
                logger.warning("A2A: Unknown skillId, falling back to planner", skill_id=skill_id)

        try:
            await super().run_task(params)
        finally:
            agent._a2a_target_action = None


def create_a2a_app(agent: GraphAgentAdapter, url: str = "http://localhost:8080/api/a2a/") -> FastA2A:
    """Create an A2A (Agent-to-Agent) app from the search agent.

    Builds the FastA2A app, broker, storage, and worker manually (instead of
    using ``agent_to_a2a``) so that the worker lifecycle can be tied to the
    host application's lifespan when mounted as a sub-app.

    Args:
        agent: The GraphAgentAdapter instance to expose via A2A.
        url: The public URL where the A2A endpoint is accessible.

    Returns:
        A FastA2A Starlette application to be mounted in the main app.
        The ``_a2a_worker`` and ``_a2a_agent`` attributes are set on the app
        so that the host can start them in its own startup/shutdown hooks.
    """
    storage = InMemoryStorage()
    broker = InMemoryBroker()
    worker = SkillAwareWorker(agent=agent, broker=broker, storage=storage)  # type: ignore[arg-type]

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
