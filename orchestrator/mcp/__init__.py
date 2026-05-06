# Copyright 2019-2026 ESnet.
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

"""MCP (Model Context Protocol) server for orchestrator-core.

Exposes workflow operations, process management, and subscription queries
as MCP tools for AI assistants like Claude.
"""

from orchestrator.mcp.server import create_mcp_app, create_mcp_server

__all__ = ["create_mcp_app", "create_mcp_server"]
