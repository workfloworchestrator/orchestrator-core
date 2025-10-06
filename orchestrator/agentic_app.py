#!/usr/bin/env python3
"""The main application module.

This module contains the main `LLMOrchestratorCore` class for the `FastAPI` backend and
provides the ability to run the CLI with LLM features (search and/or agent).
"""
# Copyright 2019-2025 SURF
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
from typing import TYPE_CHECKING, Any

import typer
from structlog import get_logger

from orchestrator.app import OrchestratorCore
from orchestrator.cli.main import app as cli_app
from orchestrator.llm_settings import LLMSettings, llm_settings

if TYPE_CHECKING:
    from pydantic_ai.models.openai import OpenAIModel
    from pydantic_ai.toolsets import FunctionToolset

logger = get_logger(__name__)


class LLMOrchestratorCore(OrchestratorCore):
    def __init__(
        self,
        *args: Any,
        llm_settings: LLMSettings = llm_settings,
        agent_model: "OpenAIModel | str | None" = None,
        agent_tools: "list[FunctionToolset] | None" = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the `LLMOrchestratorCore` class.

        This class extends `OrchestratorCore` with LLM features (search and agent).
        It runs the search migration and mounts the agent endpoint based on feature flags.

        Args:
            *args: All the normal arguments passed to the `OrchestratorCore` class.
            llm_settings: A class of settings for the LLM
            agent_model: Override the agent model (defaults to llm_settings.AGENT_MODEL)
            agent_tools: A list of tools that can be used by the agent
            **kwargs: Additional arguments passed to the `OrchestratorCore` class.

        Returns:
            None
        """
        self.llm_settings = llm_settings
        self.agent_model = agent_model or llm_settings.AGENT_MODEL
        self.agent_tools = agent_tools

        super().__init__(*args, **kwargs)

        # Run search migration if search or agent is enabled
        if self.llm_settings.SEARCH_ENABLED or self.llm_settings.AGENT_ENABLED:
            logger.info("Running search migration")
            try:
                from orchestrator.db import db
                from orchestrator.search.llm_migration import run_migration

                with db.engine.begin() as connection:
                    run_migration(connection)
            except ImportError as e:
                logger.error(
                    "Unable to run search migration. Please install search dependencies: "
                    "`pip install orchestrator-core[search]`",
                    error=str(e),
                )
                raise

        # Mount agent endpoint if agent is enabled
        if self.llm_settings.AGENT_ENABLED:
            logger.info("Initializing agent features", model=self.agent_model)
            try:
                from orchestrator.search.agent import build_agent_router

                agent_app = build_agent_router(self.agent_model, self.agent_tools)
                self.mount("/agent", agent_app)
            except ImportError as e:
                logger.error(
                    "Unable to initialize agent features. Please install agent dependencies: "
                    "`pip install orchestrator-core[agent]`",
                    error=str(e),
                )
                raise


main_typer_app = typer.Typer()
main_typer_app.add_typer(cli_app, name="orchestrator", help="The orchestrator CLI commands")

if __name__ == "__main__":
    main_typer_app()
