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

from typing import Any

import structlog
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.agent import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import FunctionToolset

from orchestrator.search.agent.prompts import get_base_instructions, get_dynamic_instructions
from orchestrator.search.agent.state import SearchState
from orchestrator.search.agent.tools import search_toolset

logger = structlog.get_logger(__name__)


def build_agent_instance(
    model: str | OpenAIChatModel, agent_tools: list[FunctionToolset[Any]] | None = None
) -> Agent[StateDeps[SearchState], str]:
    """Build and configure the search agent instance.

    Args:
        model: The LLM model to use (string or OpenAIChatModel instance)
        agent_tools: Optional list of additional toolsets to include

    Returns:
        Configured Agent instance with StateDeps[SearchState] dependencies

    Raises:
        Exception: If agent initialization fails
    """
    toolsets = agent_tools + [search_toolset] if agent_tools else [search_toolset]

    agent = Agent(
        model=model,
        deps_type=StateDeps[SearchState],
        model_settings=ModelSettings(
            parallel_tool_calls=False,
        ),  # https://github.com/pydantic/pydantic-ai/issues/562
        toolsets=toolsets,
    )
    agent.instructions(get_base_instructions)
    agent.instructions(get_dynamic_instructions)

    return agent
