#!/usr/bin/env python3
"""The main application module.

This module contains the main `AgenticOrchestratorCore` class for the `FastAPI` backend and
provides the ability to run the CLI.
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
from typing import Any

import typer
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.toolsets import FunctionToolset
from structlog import get_logger

from orchestrator.app import OrchestratorCore
from orchestrator.cli.main import app as cli_app
from orchestrator.llm_settings import LLMSettings, llm_settings
from orchestrator.search.llm_migration import run_migration

logger = get_logger(__name__)


class AgenticOrchestratorCore(OrchestratorCore):
    def __init__(
        self,
        *args: Any,
        llm_model: OpenAIModel | str = "gpt-4o-mini",
        llm_settings: LLMSettings = llm_settings,
        agent_tools: list[FunctionToolset] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the `AgenticOrchestratorCore` class.

        This class takes the same arguments as the `OrchestratorCore` class.

        Args:
            *args: All the normal arguments passed to the `OrchestratorCore` class.
            llm_model: An OpenAI model class or string, not limited to OpenAI models (gpt-4o-mini etc)
            llm_settings: A class of settings for the LLM
            agent_tools: A list of tools that can be used by the agent
            **kwargs: Additional arguments passed to the `OrchestratorCore` class.

        Returns:
            None
        """
        self.llm_model = llm_model
        self.agent_tools = agent_tools
        self.llm_settings = llm_settings

        super().__init__(*args, **kwargs)

        logger.info("Initializing LLM features")
        self._run_llm_migration()
        self.register_llm_integration()

    def _run_llm_migration(self) -> None:
        """Run LLM-specific database migration.

        This method sets up the database schema required for LLM functionality,
        including the ai_search_index table and PostgreSQL extensions (such as pgvector).

        Returns:
            None

        Raises:
            Exception: If the migration fails, typically due to missing pgvector extension
        """

        logger.info("Running LLM migration")
        try:
            from orchestrator.db import db

            with db.engine.connect() as connection:
                run_migration(connection)

        except Exception as e:
            logger.error("Failed to run LLM migration. Please ensure pgvector extension is installed.", error=str(e))
            raise

    def register_llm_integration(self) -> None:
        """Register the Agent endpoint.

        This helper includes the agent router on the application with auth dependencies.

        Returns:
            None

        """
        from fastapi import Depends

        from orchestrator.search.agent import build_agent_router
        from orchestrator.security import authorize

        agent_router = build_agent_router(self.llm_model, self.agent_tools)
        self.include_router(agent_router, prefix="/agent", dependencies=[Depends(authorize)])


main_typer_app = typer.Typer()
main_typer_app.add_typer(cli_app, name="orchestrator", help="The orchestrator CLI commands")

if __name__ == "__main__":
    main_typer_app()
