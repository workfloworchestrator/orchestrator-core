# Copyright 2019-2025 SURF.
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
from importlib import import_module

import structlog

logger = structlog.get_logger(__name__)

try:
    import_module("pydantic_ai")
except ImportError:
    logger.error(
        "LLM dependencies not installed, but LLM_ENABLED. Please install the orchestrator-core package as follows: orchestrator-core[llm], exiting now"
    )
    exit(1)
