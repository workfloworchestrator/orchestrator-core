import structlog
from fastapi import FastAPI, HTTPException
from starlette.types import ASGIApp

from orchestrator.settings import app_settings

logger = structlog.get_logger(__name__)


def _disabled_agent_app(reason: str) -> FastAPI:
    app = FastAPI(title="Agent disabled")

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def _disabled(path: str) -> None:
        raise HTTPException(status_code=503, detail=f"Agent disabled: {reason}")

    return app


def build_agent_app() -> ASGIApp:
    if not app_settings.AGENT_MODEL or not app_settings.OPENAI_API_KEY:
        logger.warning("Agent route disabled: missing model or OPENAI_API_KEY")
        return _disabled_agent_app("missing configuration")

    try:
        from pydantic_ai.ag_ui import StateDeps
        from pydantic_ai.agent import Agent
        from pydantic_ai.settings import ModelSettings

        from orchestrator.search.agent.prompts import get_base_instructions, get_dynamic_instructions
        from orchestrator.search.agent.state import SearchState
        from orchestrator.search.agent.tools import search_toolset
    except ImportError:
        logger.error(
            "\nRequired packages not installed:\n"
            "WARNING: These packages are NOT compatible with the current "
            "pydantic version in orchestrator-core.\n Upgrading pydantic to install "
            "may cause incompatibilities or runtime errors.\n\n"
            "  pydantic-ai==0.7.0\n"
            "  ag-ui-protocol>=0.1.8\n\n"
            "Install them locally to enable the agent:\n"
            "  pip install 'pydantic-ai==0.7.0' 'ag-ui-protocol>=0.1.8'\n"
        )
        logger.warning("Agent route disabled: Missing required packages")
        return _disabled_agent_app("Missing required packages")

    try:
        agent = Agent(
            model=app_settings.AGENT_MODEL,
            deps_type=StateDeps[SearchState],
            model_settings=ModelSettings(
                parallel_tool_calls=False
            ),  # https://github.com/pydantic/pydantic-ai/issues/562
            toolsets=[search_toolset],
        )
        agent.instructions(get_base_instructions)
        agent.instructions(get_dynamic_instructions)

        return agent.to_ag_ui(deps=StateDeps(SearchState()))
    except Exception as e:
        logger.error("Agent init failed; serving disabled stub.", error=str(e))
        return _disabled_agent_app(str(e))
