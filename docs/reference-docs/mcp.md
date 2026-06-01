# MCP Server

The `orchestrator-core` ships with an [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that exposes a curated subset of REST operations as **tools** for LLM agents. It is mounted on the FastAPI app at `/mcp` and shares the same authentication/authorization chain as the rest of the API.

The server is built on top of [`fastmcp`](https://gofastmcp.com/) and is **auto-generated from the FastAPI routes** — there is no separate tool registry to maintain. Tagging a route is the only thing needed to surface it.

## Enabling

The MCP sub-app is opt-in:

1. Install the optional dependency:

    ```bash
    pip install "orchestrator-core[mcp]"
    ```

2. Set the environment variable:

    ```bash
    MCP_ENABLED=True
    ```

When enabled, `OrchestratorCore.__init__` mounts the sub-app at `/mcp` and composes its ASGI lifespan into the parent app's lifespan so the streamable HTTP session manager starts and stops with the orchestrator.

Transport: **streamable HTTP** (`/mcp/`). Configure your MCP client (e.g. Claude Desktop, an agent framework) to talk to that URL.

## Usage

Once enabled, any MCP client can connect to `https://<your-orchestrator>/mcp/` and call the generated tools.

Authentication uses the same bearer token as the REST API: the `Authorization` header on the inbound MCP request is forwarded into the in-process call so each route's `Depends(authorize)` fires normally. See [Auth(n|z)](auth-backend-and-frontend.md).

The default toolset covers the typical agent flow:

| Tool                                      | Purpose                                              |
|-------------------------------------------|------------------------------------------------------|
| `list_workflows`                          | Discover available workflows                         |
| `get_workflow_form`                       | Fetch a workflow's input form (page by page)         |
| `get_subscription_available_workflows`    | List workflows available on a subscription          |
| `create_workflow` / `resume_process`      | Start or resume a process                            |
| `get_process_status`                      | Inspect a running/suspended process                  |
| `list_recent_processes`                   | List recent processes (with typed filters)           |
| `search_subscriptions`                    | Search subscriptions with typed filters              |
| `get_subscription_details`                | Get a flat header for a subscription                 |
| `list_products`                           | List products                                        |
| `get_product`                             | Get one product definition by id                     |
| `get_product_block`                       | Get one product block definition by id               |
| `get_resource_type`                       | Get one resource type definition by id               |
| `get_workflow_by_id`                      | Get one workflow definition by id                    |
| `get_subscription_domain_model`           | Get a subscription's full product-block tree (large) |
| `get_process_status_counts`               | Aggregate process/task counts grouped by status      |

Tool names map 1:1 to the route's `operation_id`; tool descriptions come from the route's docstring; parameter schemas come from the route's Pydantic request model.

## Extending

To expose a new tool, add a FastAPI route tagged with `AgentTag.EXPOSED`. The route is then picked up automatically on the next app start — no MCP-specific glue code required.

```python
from orchestrator.core.agent_tags import AgentTag
from fastapi import APIRouter

router = APIRouter()


@router.post(
    "/cancel_process",
    response_model=CancelProcessResponse,
    tags=[AgentTag.EXPOSED],
    operation_id="cancel_process",
)
def cancel_process_endpoint(params: CancelProcessRequest) -> CancelProcessResponse:
    """Cancel a running workflow process.

    Use this when a process is stuck and must be aborted.
    """
    ...
```

Guidelines:

* **Always set `operation_id`** — this becomes the MCP tool name.
* **Write a docstring** — this becomes the tool description the LLM sees. Be explicit about preconditions and side effects.
* **Use typed Pydantic models** for inputs/outputs — the parameter schema is derived from them.
* **Add `AgentTag.LARGE`** when the response may contain many records, so clients can warn the agent to narrow before calling.
* **Tag read-only `POST`/`PUT` routes `AgentTag.READONLY`** and irreversible mutations `AgentTag.DESTRUCTIVE` — these drive the tool's annotations (see below).
* Prefer placing LLM-specific routes in `orchestrator/core/api/api_v1/endpoints/mcp_tools.py`. Use this when the existing REST shape is not LLM-friendly (e.g. flat positional filters, deprecated routes, oversized payloads). See the module docstring for the rationale of each existing curated tool.

Routes without `AgentTag.EXPOSED` are excluded from the MCP surface, regardless of whether they are public REST endpoints.

## Tool annotations

Every generated tool carries [MCP `ToolAnnotations`](https://modelcontextprotocol.io/) so clients can reason about safety (e.g. auto-approve reads). They are stamped by `orchestrator.core.mcp.server._annotate` (the fastmcp `mcp_component_fn` hook), derived from each route's HTTP method plus its `AgentTag`s:

* `readOnlyHint` — `GET` routes, or any route tagged `AgentTag.READONLY`.
* `idempotentHint` — read-only routes, or `PUT`/`DELETE`.
* `destructiveHint` — `DELETE` routes, or any route tagged `AgentTag.DESTRUCTIVE`.
* `openWorldHint` — always `False` (the orchestrator acts on its own database, not an open external world).
* `title` — a humanized form of the `operation_id` (e.g. `get_process_status` → "Get Process Status").

The curated read tools in `mcp_tools.py` are `POST` routes, so they must be tagged `AgentTag.READONLY` to be marked safe; an irreversible action such as `abort_workflow_process` is tagged `AgentTag.DESTRUCTIVE`.

## Implementation

The mount logic lives in `orchestrator/core/mcp/server.py`:

```
OrchestratorCore (FastAPI)
  └── /mcp  (Starlette sub-app, fastmcp streamable HTTP)
        └── FastMCP.from_fastapi(app, route_maps=[EXPOSED → TOOL, * → EXCLUDE])
              └── in-process httpx (ASGITransport) → FastAPI route
                    └── Depends(authorize)
```

Two things are worth noting:

1. **In-process invocation** — `fastmcp` calls the FastAPI routes through `httpx` over an `ASGITransport`. The request goes through the normal middleware + dependency chain, so authorization and exception handlers behave exactly as for an external REST call.
2. **Authorization header forwarding** — `fastmcp`'s default `get_http_headers` excludes `authorization`. `orchestrator.core.mcp.server._forward_auth_header` is registered as an httpx request hook to re-inject it so `Depends(authorize)` can validate the bearer token. See [fastmcp#2817](https://github.com/jlowin/fastmcp/issues/2817).
