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

"""This is the orchestrator workflow engine."""

__version__ = "5.0.0a1"


from structlog import get_logger

logger = get_logger(__name__)

logger.info("Starting the orchestrator", version=__version__)

from orchestrator.app import OrchestratorCore
from orchestrator.llm_settings import llm_settings
from orchestrator.settings import app_settings
from orchestrator.workflow import begin, conditional, done, focussteps, inputstep, retrystep, step, steplens, workflow

__all__ = [
    "OrchestratorCore",
    "app_settings",
    "step",
    "inputstep",
    "workflow",
    "retrystep",
    "begin",
    "done",
    "conditional",
    "focussteps",
    "steplens",
]

if llm_settings.LLM_ENABLED:
    try:
        from importlib import import_module

        import_module("pydantic_ai")
        from orchestrator.agentic_app import AgenticOrchestratorCore  # noqa: F401

        __all__ = __all__ + ["llm_settings", "AgentOrchestratorCore"]
    except ImportError:
        logger.error(
            "Unable to import 'pydantic_ai' module, please install the orchestrator with llm dependencies. `pip install orchestrator-core[llm]",
        )
        exit(1)
