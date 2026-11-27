# Copyright 2019-2026 SURF, GÉANT, ESnet.
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

from importlib.metadata import version

__version__: str = version("orchestrator-core")


from structlog import get_logger

logger = get_logger(__name__)

logger.info("Starting the orchestrator", version=__version__)

# App settings must resolve before OrchestratorCore
from orchestrator.core.settings import app_settings, llm_settings
from orchestrator.core.app import OrchestratorCore
from orchestrator.core.workflow import (
    begin,
    conditional,
    done,
    focussteps,
    inputstep,
    retrystep,
    step,
    steplens,
    workflow,
)

__all__ = [
    "OrchestratorCore",
    "app_settings",
    "llm_settings",
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
