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

from dataclasses import dataclass
from typing import Any, Callable

from pydantic_ai.toolsets import AbstractToolset

from orchestrator.search.agent.memory import MemoryScope
from orchestrator.search.agent.prompts import (
    get_aggregation_execution_prompt,
    get_result_actions_prompt,
    get_search_execution_prompt,
    get_text_response_prompt,
)
from orchestrator.search.agent.state import SearchState, TaskAction
from orchestrator.search.agent.tools import (
    aggregation_execution_toolset,
    aggregation_toolset,
    filter_building_toolset,
    result_actions_toolset,
    search_execution_toolset,
)


@dataclass(frozen=True)
class Skill:
    """Declarative capability definition (A2A sense, not Anthropic Agent Skills).

    In the A2A protocol, one agent advertises many skills — discrete
    capabilities with metadata (name, description, tags). Our Skill
    extends that with runtime wiring: toolsets, prompt function, and
    memory scope. The agent creates pydantic-ai Agent instances from
    skills at execution time.

    Note: Anthropic's "Agent Skills" are a different concept; filesystem-based
    instruction packages (SKILL.md) for teaching Claude workflows.
    """

    action: TaskAction
    name: str
    description: str
    tags: list[str]
    toolsets: list[AbstractToolset[Any]]
    get_prompt: Callable[[SearchState], str]
    memory_scope: MemoryScope


SKILLS: dict[TaskAction, Skill] = {
    TaskAction.SEARCH: Skill(
        action=TaskAction.SEARCH,
        name="Search",
        description="Find subscriptions, products, workflows, processes",
        tags=["search", "query"],
        toolsets=[filter_building_toolset, search_execution_toolset],
        get_prompt=get_search_execution_prompt,
        memory_scope=MemoryScope.LIGHTWEIGHT,
    ),
    TaskAction.AGGREGATION: Skill(
        action=TaskAction.AGGREGATION,
        name="Aggregate",
        description="Count, sum, avg with grouping",
        tags=["aggregate", "analytics"],
        toolsets=[filter_building_toolset, aggregation_toolset, aggregation_execution_toolset],
        get_prompt=get_aggregation_execution_prompt,
        memory_scope=MemoryScope.LIGHTWEIGHT,
    ),
    TaskAction.RESULT_ACTIONS: Skill(
        action=TaskAction.RESULT_ACTIONS,
        name="Result Actions",
        description="Export results or fetch entity details",
        tags=["export", "details"],
        toolsets=[result_actions_toolset],
        get_prompt=get_result_actions_prompt,
        memory_scope=MemoryScope.MINIMAL,
    ),
    TaskAction.TEXT_RESPONSE: Skill(
        action=TaskAction.TEXT_RESPONSE,
        name="Text Response",
        description="Answer general questions about the system",
        tags=["text", "help"],
        toolsets=[],
        get_prompt=get_text_response_prompt,
        memory_scope=MemoryScope.LIGHTWEIGHT,
    ),
}
