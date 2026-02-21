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


from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncIterator

import structlog
from pydantic_ai import Agent
from pydantic_ai.ag_ui import StateDeps

from orchestrator.search.agent.events import RunContext, make_step_active_event
from orchestrator.search.agent.memory import MemoryScope, ToolStep
from orchestrator.search.agent.prompts import get_planning_prompt
from orchestrator.search.agent.skill_runner import SkillRunner
from orchestrator.search.agent.state import ExecutionPlan, SearchState, Task, TaskAction, TaskStatus
from orchestrator.search.agent.utils import log_agent_request, log_execution_plan

if TYPE_CHECKING:
    from orchestrator.search.agent.skills import Skill

logger = structlog.get_logger(__name__)


@dataclass
class Planner:
    """Creates and executes plans via LLM.

    Owns the full plan lifecycle: create plan, iterate tasks,
    run SkillRunners, handle replanning on failure.
    """

    model: str
    skills: dict[TaskAction, Skill]
    debug: bool = False

    def __post_init__(self):
        self._agent = Agent(
            model=self.model,
            deps_type=StateDeps[SearchState],
            output_type=ExecutionPlan,
            name="create_execution_plan",
            retries=2,
        )

    async def _create_plan(self, ctx: RunContext) -> ExecutionPlan:
        """Create an execution plan via LLM."""
        ctx.state.memory.start_step("Planner")

        logger.info("Planner: Creating execution plan")

        message_history = ctx.state.memory.get_message_history(max_turns=5, scope=MemoryScope.FULL)
        prompt = get_planning_prompt(ctx.state)

        if self.debug:
            log_agent_request("Planner", prompt, message_history)

        result = await self._agent.run(
            instructions=prompt, message_history=message_history, deps=StateDeps(ctx.state)
        )

        plan = result.output

        if self.debug:
            log_execution_plan(plan)

        logger.info(
            "Planner: Plan created",
            num_tasks=len(plan.tasks),
            tasks=[f"{i+1}. {t.reasoning}" for i, t in enumerate(plan.tasks)],
        )

        return plan

    async def _run_tasks(self, ctx: RunContext, tasks: list[Task]) -> AsyncIterator[Any]:
        """Execute tasks sequentially, yielding events. Sets task.status on each."""
        for task in tasks:
            skill = self.skills.get(task.action_type)
            if not skill:
                logger.warning(f"Unknown task type: {task.action_type}, skipping")
                continue

            if task.action_type in (TaskAction.SEARCH, TaskAction.AGGREGATION):
                ctx.state.query = None
                ctx.state.pending_filters = None

            task.status = TaskStatus.EXECUTING
            runner = SkillRunner(skill=skill, model=self.model, debug=self.debug)

            try:
                async for event in runner.run(ctx, reasoning=task.reasoning):
                    yield event
                task.status = TaskStatus.COMPLETED
            except Exception as e:
                logger.error(f"Task failed: {task.action_type}", error=str(e))
                task.status = TaskStatus.FAILED
                ctx.state.memory.record_tool_step(
                    ToolStep(step_type="error", description=f"{skill.name} failed: {e}",
                             success=False, error_message=str(e))
                )
                break

    async def execute(
        self, ctx: RunContext, *, target_action: TaskAction | None = None
    ) -> AsyncIterator[Any]:
        """Create and execute a plan, streaming all events.

        Args:
            ctx: Current run context
            target_action: If set, skip planning and execute this single action directly
        """
        if target_action:
            tasks = [Task(action_type=target_action, reasoning="Direct invocation")]
        else:
            yield make_step_active_event("Planner")
            tasks = (await self._create_plan(ctx)).tasks

        async for event in self._run_tasks(ctx, tasks):
            yield event
