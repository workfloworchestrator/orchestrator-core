#!/usr/bin/env python3
"""Demo: MCP client that exercises the agent's MCP tools.

Usage:
    uv run demos/mcp_client.py                                    # run all tools
    uv run demos/mcp_client.py search "active subscriptions"      # single tool
    uv run demos/mcp_client.py get_entity_details SUBSCRIPTION <uuid>
"""

import asyncio
import json
import sys

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://localhost:8080/api/agent/mcp"
SMOKE_TESTS = [
    ("search", {"query": "show me active subscriptions"}),
    ("aggregate", {"query": "count subscriptions by product"}),
    ("ask", {"query": "what types of data can you search?"}),
]


async def call_tool(session: ClientSession, name: str, args: dict) -> None:
    print(f"\n>>> {name}({json.dumps(args)})")
    result = await session.call_tool(name, arguments=args)
    for block in result.content:
        text = getattr(block, "text", None) or str(block)
        try:
            text = json.dumps(json.loads(text), indent=2)
        except (json.JSONDecodeError, TypeError):
            pass
        print(text)


async def main(tools: list[tuple[str, dict]]) -> None:
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for name, args in tools:
                await call_tool(session, name, args)


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        asyncio.run(main(SMOKE_TESTS))
    elif argv[0] == "get_entity_details" and len(argv) >= 3:
        asyncio.run(main([(argv[0], {"entity_type": argv[1], "entity_id": argv[2]})]))
    elif len(argv) >= 2:
        asyncio.run(main([(argv[0], {"query": " ".join(argv[1:])})]))
    else:
        print(__doc__)
