# Copyright 2019-2026 SURF, GÉANT.
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

"""Per-endpoint metadata for LLM agent exposure.

Add these as FastAPI route ``tags=[...]`` to mark endpoints for downstream
consumers. Each tag is a short kebab-case string that lands unchanged in the
OpenAPI spec, so any tool reading the spec can filter/branch on it.

"""

from enum import Enum


class AgentTag(str, Enum):
    """Per-endpoint metadata for LLM agent exposure."""

    EXPOSED = "agent-exposed"
    """Gate: if absent, the endpoint is not exposed to any LLM agent surface."""

    LARGE = "agent-large"
    """Signal: may return many records; agent should narrow before calling."""
