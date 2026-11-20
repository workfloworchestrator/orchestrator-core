---
# tutorial | how-to | reference | explanation | mixed
diataxis: mixed
reviewed: false
---

# MCP Server
<!-- diataxis: mixed -->

The `orchestrator-core` ships with an [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that exposes a curated subset of REST operations as **tools** for LLM agents. It is mounted on the FastAPI app at `/mcp` and shares the same authentication/authorization chain as the rest of the API.

The server is built on top of [`fastmcp`](https://gofastmcp.com/) and is **auto-generated from the FastAPI routes** — there is no separate tool registry to maintain. Tagging a route is the only thing needed to surface it.

## Enabling
<!-- diataxis: -->

The MCP sub-app is opt-in:

1. Install the optional dependency:

    ```shell
    pip install "orchestrator-core[mcp]"
    ```

2. Set the environment variable:

    ```shell
    MCP_ENABLED=True
    ```

When enabled, `OrchestratorCore.__init__` mounts the sub-app at `/mcp` and composes its ASGI lifespan into the parent app's lifespan so the stream-able HTTP session manager starts and stops with the orchestrator.

Transport: **streamable HTTP** (`/mcp/`). Configure your MCP client (e.g. Claude Desktop, an agent framework) to talk to that URL.

## Usage
<!-- diataxis: -->

Once enabled, any MCP client can connect to `https://<your-orchestrator>/mcp/` and call the generated tools.

Authentication uses the same bearer token as the REST API: the `Authorization` header on the inbound MCP request is forwarded into the in-process call so each route's `Depends(authorize)` fires normally. See [Auth(n|z)](auth-backend-and-frontend.md).

The default toolset covers the typical agent flow:

| Tool                                      | Purpose                                              |
|-------------------------------------------|------------------------------------------------------|
| `list_workflows`                          | Discover available workflows                         |
| `get_workflow_form`                       | Fetch a workflow's input form (page by page)         |
| `get_workflow_form_options`               | Find the options of a form field with a long list    |
| `get_subscription_available_workflows`    | List workflows available on a subscription          |
| `create_workflow`                         | Start a new workflow process                         |
| `resume_workflow_process`                 | Resume a suspended process with form input           |
| `abort_workflow_process`                  | Abort a running process (irreversible)               |
| `get_process_status`                      | Inspect a running/suspended process                  |
| `list_recent_processes`                   | List recent processes (with typed filters)           |
| `list_subscriptions`                      | List subscriptions, newest first                     |
| `list_products`                           | List products                                        |
| `get_product`                             | Get one product definition by id                     |
| `get_product_block`                       | Get one product block definition by id               |
| `get_resource_type`                       | Get one resource type definition by id               |
| `get_workflow_by_id`                      | Get one workflow definition by id                    |
| `get_subscription_domain_model`           | Get a subscription's full product-block tree (large) |
| `get_process_status_counts`               | Aggregate process/task counts grouped by status      |

On top of these, [AI / Hybrid Search](ai-search.md#what-you-can-search-and-where) contributes the `search`, `aggregate`, `discover_filter_paths`, `get_valid_operators`, `resolve_entity` and `export_query` tools.

Tool names map 1:1 to the route's `operation_id`; tool descriptions come from the route's docstring; parameter schemas come from the route's Pydantic request model.

## Workflow form pages for agents
<!-- diataxis: reference -->

`get_workflow_form` walks a workflow's form page by page. Each result describes one page as `schema`: the page's JSON Schema as one self-contained document, the same schema the browser renders but with every `$ref` replaced by its definition (a model that contains itself keeps its `$ref` and its entry under `$defs`). Read `properties` and `required` for what to submit. A property's `title` and `description` are the field's label and help text as the frontend shows them, from core's form translations in the `language` asked (default `en-GB`); a field without one keeps the schema's own title. A property with `readOnly: true` (a label, a divider, a summary table, a subscription shown for context) is shown to a person and takes no value: submit nothing for it. `enum` lists the values a property takes and, where a value has a label that differs from it, `options` maps value to label: submit the value. `format: "accept"` is a confirmation and takes `"ACCEPTED"`. A nullable property is an `anyOf` with `{"type": "null"}`. The form's widget hints (`format`, `uniforms` / `extraProperties`) are in the schema as the browser gets them; the products a `productId` field allows, for instance, are under `uniforms.productIds`.

`status` says what to do next: `next` (fill the page and call again with it appended to `page_inputs`), `complete` (call `create_workflow` with the same `page_inputs`) or `rejected`. A page that does not validate is reported as a tool error by default; with `verdict: "result"` it comes back as a result with `status: "rejected"`, `errors` (`loc`, `msg`, `type`) and the page's `schema`, so the caller can correct the values named and resubmit that page. `create_workflow` validates the pages again, so nothing starts on an ignored verdict.

A field that says where its options are fetched (pydantic-forms' `OptionsSource`, `optionsSource` in the schema) is read by core, in process and with the caller's `Authorization` header; only a route of the same API is read. A list of at most ten options is written into the schema as `enum` and `options`. A longer list, or one that depends on another field of the page, keeps its `optionsSource`: `get_workflow_form_options` returns its options (whole when at most `limit` of them, else narrowed by `search`: by the source's own `search` parameter when it declares one, which a list that can grow long should, else to the options whose label or value contains the text) and takes the values of the page's other fields in `page_values`. The form itself takes any string for such a field, so `get_workflow_form` rejects a submitted value that is not among the source's options, and returns under `labels` how the accepted page's sourced values are shown to a person. A source that cannot be read is not checked. A source that declares a `search` parameter may return only part of its list without a term, so it is never written into the schema. When it also declares `lookup`, a submitted value is checked and labelled through that; without one the value is accepted as it came, unlabelled.

The walk and the schema are pydantic-forms': `pydantic_forms.core.walk_form` gives the next page, the result or the rejected page; `pydantic_forms.core.page_schema(page, inline_refs=True)` renders the page; `pydantic_forms.core.form_errors` turns a rejection into `errors`. Core keeps no copy of them.

## Extending
<!-- diataxis: how-to -->

Expose a FastAPI route by adding `AGENT_EXPOSED_TAG` to its `tags`, and declare its behavior through
`openapi_extra`. Import the tag and annotation constants from `orchestrator.core.mcp.server`:

```python
from fastapi import APIRouter

from orchestrator.core.mcp.server import AGENT_EXPOSED_TAG, DESTRUCTIVE_TOOL

router = APIRouter()


@router.post(
    "/cancel_process",
    response_model=CancelProcessResponse,
    tags=[AGENT_EXPOSED_TAG],
    operation_id="cancel_process",
    openapi_extra=DESTRUCTIVE_TOOL,
)
def cancel_process_endpoint(params: CancelProcessRequest) -> CancelProcessResponse:
    """Cancel a running workflow process.

    Use this when a process is stuck and must be aborted.
    """
    ...
```

Use your application's request and response models and cancellation implementation in this example.
Include the router in the FastAPI app before its MCP tools are built, then restart the app.

Guidelines:

* **Always set `operation_id`**: this becomes the MCP tool name.
* **Write a docstring**: this becomes the tool description the LLM sees. State preconditions and side effects.
* **Use typed Pydantic models** for inputs and outputs: they define the parameter and response schemas.
* **Declare behavior with `openapi_extra`**: use `READONLY_TOOL` for reads, `WRITE_TOOL` for non-idempotent
  mutations, `IDEMPOTENT_WRITE_TOOL` for idempotent mutations, or `DESTRUCTIVE_TOOL` for irreversible operations.
  Choose according to the route's behavior, not just its HTTP method.
* Prefer placing LLM-specific routes in `orchestrator/core/api/api_v1/endpoints/mcp_tools.py` when the existing REST
  shape is not LLM-friendly, for example because of positional filters, deprecated routes or oversized responses.
  Describe large responses and useful ways to narrow them in the docstring.

Routes without `AGENT_EXPOSED_TAG` are excluded from this MCP server's tools, regardless of whether they are
public REST endpoints. Annotation hints do not replace authorization or collect approval from a person.

## Tool annotations
<!-- diataxis: reference -->

The `openapi_extra` constants in `orchestrator.core.mcp.server` contain an `x-mcp-annotations` dictionary.
`_build_component_fn` reads that dictionary from the app's OpenAPI specification, matches it by `operationId`,
and applies it to the generated tool's [MCP `ToolAnnotations`](https://modelcontextprotocol.io/).

| Constant | `readOnlyHint` | `idempotentHint` | `destructiveHint` | `openWorldHint` |
| --- | --- | --- | --- | --- |
| `READONLY_TOOL` | `True` | `True` | `False` | `False` |
| `WRITE_TOOL` | `False` | `False` | `False` | `False` |
| `IDEMPOTENT_WRITE_TOOL` | `False` | `True` | `False` | `False` |
| `DESTRUCTIVE_TOOL` | `False` | `True` | `True` | `False` |

For a route with this extension, `title` defaults to a humanized `operation_id`, such as
`get_process_status` becoming "Get Process Status". An explicit `title` in the annotation dictionary overrides it.
Without the extension, this callback leaves the generated component's annotations unchanged; it does not infer
these hints from the HTTP method.

The curated read tools in `mcp_tools.py` use `POST` with `openapi_extra=READONLY_TOOL`. An irreversible operation
such as `abort_workflow_process` uses `openapi_extra=DESTRUCTIVE_TOOL`.

## Implementation
<!-- diataxis: explanation -->

The mount logic lives in `orchestrator/core/mcp/server.py`:

```text
OrchestratorCore (FastAPI)
  └── /mcp  (Starlette sub-app, fastmcp streamable HTTP)
        └── FastMCP.from_fastapi(app, route_maps=[AGENT_EXPOSED_TAG → TOOL, * → EXCLUDE])
              └── in-process httpx (ASGITransport) → FastAPI route
                    └── Depends(authorize)
```

Two things are worth noting:

1. **In-process invocation** — `fastmcp` calls the FastAPI routes through `httpx` over an `ASGITransport`. The request goes through the normal middleware + dependency chain, so authorization and exception handlers behave exactly as for an external REST call.
2. **Authorization header forwarding** — `fastmcp`'s default `get_http_headers` excludes `authorization`. `orchestrator.core.mcp.server._forward_auth_header` is registered as an httpx request hook to re-inject it so `Depends(authorize)` can validate the bearer token. See [fastmcp#2817](https://github.com/jlowin/fastmcp/issues/2817).
