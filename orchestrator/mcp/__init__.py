"""MCP (Model Context Protocol) server for orchestrator-core.

Exposes workflow operations, process management, and subscription queries
as MCP tools for AI assistants like Claude.
"""

from orchestrator.mcp.server import create_mcp_app, create_mcp_server

__all__ = ["create_mcp_app", "create_mcp_server"]
