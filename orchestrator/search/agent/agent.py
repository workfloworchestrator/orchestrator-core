from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.agent import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import FunctionToolset
from starlette.types import ASGIApp

from orchestrator.search.agent.prompts import get_base_instructions, get_dynamic_instructions
from orchestrator.search.agent.state import SearchState
from orchestrator.search.agent.tools import search_toolset

logger = structlog.get_logger(__name__)


def _disabled_agent_app(reason: str) -> FastAPI:
    app = FastAPI(title="Agent disabled")

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def _disabled(path: str) -> None:
        raise HTTPException(status_code=503, detail=f"Agent disabled: {reason}")

    return app


def build_agent_app(model: str | OpenAIModel, toolsets: list[FunctionToolset[Any]] | None = None) -> ASGIApp:
    try:
        toolsets = toolsets + [search_toolset] if toolsets else [search_toolset]

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

        return agent.to_ag_ui(deps=StateDeps(SearchState()))
    except Exception as e:
        logger.error("Agent init failed; serving disabled stub.", error=str(e))
        return _disabled_agent_app(str(e))
