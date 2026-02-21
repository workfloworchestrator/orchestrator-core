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
from typing import Any

import typer
from structlog import get_logger

from orchestrator.app import OrchestratorCore
from orchestrator.cli.main import app as cli_app
from orchestrator.llm_settings import LLMSettings, llm_settings

logger = get_logger(__name__)


class LLMOrchestratorCore(OrchestratorCore):
    def __init__(
        self,
        *args: Any,
        llm_settings: LLMSettings = llm_settings,
        agent_model: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the `LLMOrchestratorCore` class.

        This class extends `OrchestratorCore` with LLM features (search and agent).
        It runs the search migration based on feature flags.

        Args:
            *args: All the normal arguments passed to the `OrchestratorCore` class.
            llm_settings: A class of settings for the LLM
            agent_model: Override the agent model (defaults to llm_settings.AGENT_MODEL)
            **kwargs: Additional arguments passed to the `OrchestratorCore` class.

        Returns:
            None
        """
        self.llm_settings = llm_settings
        self.agent_model = agent_model or llm_settings.AGENT_MODEL

        super().__init__(*args, **kwargs)

        # Mount A2A endpoint if agent is enabled
        if self.llm_settings.AGENT_ENABLED:
            from orchestrator.search.agent.adapters.a2a import create_a2a_app, start_a2a
            from orchestrator.search.agent.agent import build_agent_instance

            a2a_agent = build_agent_instance(self.agent_model, debug=self.llm_settings.AGENT_DEBUG)
            a2a_app = create_a2a_app(a2a_agent)
            self.mount("/api/a2a", a2a_app)

            # FastA2A's lifespan doesn't run when mounted as sub-app,
            # so we start the task manager + worker via host app events.
            _a2a_stack = None

            async def _start_a2a() -> None:
                nonlocal _a2a_stack
                _a2a_stack = await start_a2a(a2a_app)

            async def _stop_a2a() -> None:
                if _a2a_stack:
                    await _a2a_stack.__aexit__(None, None, None)

            self.add_event_handler("startup", _start_a2a)
            self.add_event_handler("shutdown", _stop_a2a)

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


main_typer_app = typer.Typer()
main_typer_app.add_typer(cli_app, name="orchestrator", help="The orchestrator CLI commands")

if __name__ == "__main__":
    main_typer_app()
