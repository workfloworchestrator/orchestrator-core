# MCP Tool-Surface Quality + Curated GET Endpoints — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve MCP tool-selection quality by stamping `ToolAnnotations` on every generated tool and expose a curated set of GET endpoints as tools.

**Architecture:** A single `mcp_component_fn` (`_annotate`) passed to `FastMCP.from_fastapi` derives `ToolAnnotations` (readOnly/idempotent/destructive/openWorld + a humanized title) from each route's HTTP method plus two new `AgentTag` signals. Six existing GET routes gain `operation_id`, a docstring, and `AgentTag.EXPOSED` so they auto-surface as tools. The MCP build is extracted to a `build_mcp(app)` helper so tests exercise the real configuration.

**Tech Stack:** FastAPI, fastmcp 3.2.4, `mcp.types.ToolAnnotations`, pytest (+ pytest-asyncio), uv.

> NOTE: `docs/superpowers/**` is gitignored in this repo (`.gitignore:88`), so this plan file is a working artifact and is **not** committed. All *code* commits below touch tracked files normally.

> Project rules (from CLAUDE.md / session): no relative imports; line length 120; mypy strict; prefer pure/functional style; parametrize tests; commit messages descriptive with **no** `Co-Authored-By`; never disable GPG signing.

---

## File Structure

- `orchestrator/core/agent_tags.py` — **modify**: add `READONLY`, `DESTRUCTIVE` enum members.
- `orchestrator/core/mcp/server.py` — **modify**: extract `build_mcp(app)`, add `_humanize` + `_annotate`, wire `mcp_component_fn`.
- `orchestrator/core/api/api_v1/endpoints/products.py` — **modify**: tag `GET /{product_id}` → `get_product`.
- `orchestrator/core/api/api_v1/endpoints/product_blocks.py` — **modify**: tag `GET /{product_block_id}` → `get_product_block`.
- `orchestrator/core/api/api_v1/endpoints/resource_types.py` — **modify**: tag `GET /{resource_type_id}` → `get_resource_type`.
- `orchestrator/core/api/api_v1/endpoints/workflows.py` — **modify**: tag `GET /{workflow_id}` → `get_workflow_by_id`.
- `orchestrator/core/api/api_v1/endpoints/subscriptions.py` — **modify**: tag `GET /domain-model/{subscription_id}` → `get_subscription_domain_model` (+ LARGE).
- `orchestrator/core/api/api_v1/endpoints/processes.py` — **modify**: tag `GET /status-counts` → `get_process_status_counts`; add `DESTRUCTIVE` to `abort_workflow_process`.
- `orchestrator/core/api/api_v1/endpoints/mcp_tools.py` — **modify**: add `AgentTag.READONLY` to the 7 read tools.
- `test/unit_tests/mcp/test_mcp.py` — **modify**: use `build_mcp`, expand expected set (11→17), add annotation + docstring-guardrail tests, extend fixture.
- `docs/reference-docs/mcp.md` — **modify**: document new tools, tags, and annotation rules.

---

## Task 1: Extract `build_mcp(app)` (behavior-preserving refactor)

**Files:**
- Modify: `orchestrator/core/mcp/server.py`
- Test: `test/unit_tests/mcp/test_mcp.py`

- [ ] **Step 1: Refactor `server.py` to add `build_mcp` and call it from `mount_mcp`**

Replace the body of `mount_mcp` and add `build_mcp` above it. The `from __future__` is not needed. Keep the existing module docstring and `_forward_auth_header` untouched. Resulting lower half of the file:

```python
def build_mcp(app: FastAPI) -> "FastMCP":  # noqa: F821 (lazy import below)
    """Construct the configured ``FastMCP`` for ``app`` without mounting it.

    Extracted so tests can build the exact same server (route maps, component
    customization, auth-forwarding hook) the application uses at runtime.
    """
    from fastmcp import FastMCP
    from fastmcp.server.providers.openapi import MCPType, RouteMap

    return FastMCP.from_fastapi(
        app=app,
        name="orchestrator-core-mcp",
        route_maps=[
            RouteMap(tags={AgentTag.EXPOSED.value}, mcp_type=MCPType.TOOL),
            RouteMap(mcp_type=MCPType.EXCLUDE),
        ],
        httpx_client_kwargs={"event_hooks": {"request": [_forward_auth_header]}},
    )


def mount_mcp(app: FastAPI) -> Starlette:
    """Auto-generate MCP tools from ``app``'s routes, mount at ``/mcp``, return the sub-app.

    Only routes tagged with ``AgentTag.EXPOSED`` are surfaced; all other
    routes are excluded (otherwise fastmcp's default would expose every
    route in the app as a tool).

    The returned sub-app carries its own ASGI lifespan that the parent must
    enter — Starlette does not invoke a mounted sub-app's lifespan. Use
    ``mcp_app.router.lifespan_context(parent)`` from inside the parent's
    own lifespan context manager.
    """
    mcp = build_mcp(app)
    mcp_app = mcp.http_app(path="/", transport="http")
    app.mount(MCP_MOUNT_PATH, mcp_app)
    return mcp_app
```

Add the type-only import at the top of the file (under the existing imports) so the `"FastMCP"` annotation resolves for mypy without importing the optional dep at runtime:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP
```

- [ ] **Step 2: Point the existing test at `build_mcp`**

In `test/unit_tests/mcp/test_mcp.py`, replace the inline `FastMCP.from_fastapi(...)` construction inside `test_fastmcp_introspects_all_expected_tools` with the shared helper:

```python
async def test_fastmcp_introspects_all_expected_tools(app_with_agent_routes: FastAPI) -> None:
    """``build_mcp`` produces exactly the expected tools from the tagged routes."""
    pytest.importorskip("fastmcp")
    from orchestrator.core.mcp.server import build_mcp

    mcp = build_mcp(app_with_agent_routes)

    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}
    assert (
        tool_names == EXPECTED_TOOL_NAMES
    ), f"missing: {EXPECTED_TOOL_NAMES - tool_names}, extra: {tool_names - EXPECTED_TOOL_NAMES}"

    for tool in tools:
        assert isinstance(tool.parameters, dict), f"tool {tool.name} has non-dict parameters"
        assert "properties" in tool.parameters, f"tool {tool.name} parameters missing 'properties'"
```

- [ ] **Step 3: Run the MCP tests**

Run: `uv run --extra mcp pytest test/unit_tests/mcp/test_mcp.py -v`
Expected: PASS (still 11 tools, behavior unchanged).

- [ ] **Step 4: Commit**

```bash
git add orchestrator/core/mcp/server.py test/unit_tests/mcp/test_mcp.py
git commit -m "Extract build_mcp helper so tests use the real MCP configuration"
```

---

## Task 2: Add `ToolAnnotations` via `_annotate` + signal tags

**Files:**
- Modify: `orchestrator/core/agent_tags.py`
- Modify: `orchestrator/core/mcp/server.py`
- Modify: `orchestrator/core/api/api_v1/endpoints/mcp_tools.py`
- Modify: `orchestrator/core/api/api_v1/endpoints/processes.py`
- Test: `test/unit_tests/mcp/test_mcp.py`

- [ ] **Step 1: Write the failing annotation test**

Add to `test/unit_tests/mcp/test_mcp.py` (the helper + parametrized test + global test). These reference only tools that already exist after Task 1.

```python
async def _tools_by_name(app: FastAPI) -> dict[str, object]:
    from orchestrator.core.mcp.server import build_mcp

    mcp = build_mcp(app)
    return {tool.name: tool for tool in await mcp.list_tools()}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name, read_only, idempotent, destructive",
    [
        pytest.param("get_process_status", True, True, False, id="readonly-post"),
        pytest.param("search_subscriptions", True, True, False, id="readonly-search-post"),
        pytest.param("list_products", True, True, False, id="readonly-get"),
        pytest.param("create_workflow", False, False, False, id="write-post"),
        pytest.param("resume_workflow_process", False, True, False, id="idempotent-put"),
        pytest.param("abort_workflow_process", False, True, True, id="destructive-put"),
    ],
)
async def test_tool_annotations(
    app_with_agent_routes: FastAPI,
    tool_name: str,
    read_only: bool,
    idempotent: bool,
    destructive: bool,
) -> None:
    """Each tool's ToolAnnotations reflect its method + AgentTag signals."""
    pytest.importorskip("fastmcp")
    tool = (await _tools_by_name(app_with_agent_routes))[tool_name]
    ann = tool.annotations
    assert ann is not None
    assert ann.readOnlyHint is read_only
    assert ann.idempotentHint is idempotent
    assert ann.destructiveHint is destructive
    assert ann.openWorldHint is False


@pytest.mark.asyncio
async def test_all_tools_have_title_and_closed_world(app_with_agent_routes: FastAPI) -> None:
    """Every tool gets a non-empty humanized title and openWorldHint=False."""
    pytest.importorskip("fastmcp")
    for name, tool in (await _tools_by_name(app_with_agent_routes)).items():
        assert tool.annotations is not None, name
        assert tool.annotations.title, name
        assert tool.annotations.openWorldHint is False, name
```

- [ ] **Step 2: Run it to confirm failure**

Run: `uv run --extra mcp pytest test/unit_tests/mcp/test_mcp.py::test_tool_annotations -v`
Expected: FAIL — `ann is None` (no annotations stamped yet) and `readOnlyHint`/`destructiveHint` wrong for POST/PUT tools.

- [ ] **Step 3: Add the two signal tags**

In `orchestrator/core/agent_tags.py`, append inside `class AgentTag`:

```python
    READONLY = "agent-readonly"
    """Signal: a non-GET route that does NOT mutate state (read-only tool)."""

    DESTRUCTIVE = "agent-destructive"
    """Signal: an irreversible mutation (e.g. abort, delete)."""
```

- [ ] **Step 4: Add `_humanize` + `_annotate` and wire them into `build_mcp`**

In `orchestrator/core/mcp/server.py`, add these helpers above `build_mcp`:

```python
def _humanize(name: str) -> str:
    """Turn an ``operation_id`` into a human-readable tool title.

    ``get_process_status`` -> ``Get Process Status``.
    """
    return name.replace("_", " ").title()


def _annotate(route: "HTTPRoute", component: object) -> None:
    """Stamp ``ToolAnnotations`` on each generated tool (``mcp_component_fn`` hook).

    Read/idempotent/destructive hints are inferred from the HTTP method, with
    ``AgentTag.READONLY`` / ``AgentTag.DESTRUCTIVE`` overriding for POST/PUT
    routes that don't follow method semantics (e.g. the curated POST read
    tools). ``openWorldHint`` is always ``False`` — the orchestrator operates
    on its own database, not an open external world.
    """
    from fastmcp.server.providers.openapi import OpenAPITool
    from mcp.types import ToolAnnotations

    if not isinstance(component, OpenAPITool):
        return

    tags = set(route.tags or [])
    method = (route.method or "").upper()
    read_only = method == "GET" or AgentTag.READONLY.value in tags
    destructive = method == "DELETE" or AgentTag.DESTRUCTIVE.value in tags
    component.annotations = ToolAnnotations(
        title=_humanize(component.name),
        readOnlyHint=read_only,
        idempotentHint=read_only or method in {"PUT", "DELETE"},
        destructiveHint=destructive,
        openWorldHint=False,
    )
```

Extend the `TYPE_CHECKING` block at the top of the file:

```python
if TYPE_CHECKING:
    from fastmcp import FastMCP
    from fastmcp.utilities.openapi import HTTPRoute
```

Add `mcp_component_fn=_annotate` to the `FastMCP.from_fastapi(...)` call inside `build_mcp`:

```python
    return FastMCP.from_fastapi(
        app=app,
        name="orchestrator-core-mcp",
        route_maps=[
            RouteMap(tags={AgentTag.EXPOSED.value}, mcp_type=MCPType.TOOL),
            RouteMap(mcp_type=MCPType.EXCLUDE),
        ],
        mcp_component_fn=_annotate,
        httpx_client_kwargs={"event_hooks": {"request": [_forward_auth_header]}},
    )
```

- [ ] **Step 5: Tag the curated read tools `READONLY`**

In `orchestrator/core/api/api_v1/endpoints/mcp_tools.py`, add `AgentTag.READONLY` to the `tags=[...]` list of these 7 routes:

```python
# list_workflows
    tags=[AgentTag.EXPOSED, AgentTag.LARGE, AgentTag.READONLY],
# get_workflow_form
    tags=[AgentTag.EXPOSED, AgentTag.READONLY],
# get_subscription_available_workflows
    tags=[AgentTag.EXPOSED, AgentTag.READONLY],
# get_process_status
    tags=[AgentTag.EXPOSED, AgentTag.READONLY],
# list_recent_processes
    tags=[AgentTag.EXPOSED, AgentTag.LARGE, AgentTag.READONLY],
# get_subscription_details
    tags=[AgentTag.EXPOSED, AgentTag.READONLY],
# search_subscriptions
    tags=[AgentTag.EXPOSED, AgentTag.LARGE, AgentTag.READONLY],
```

- [ ] **Step 6: Tag `abort_workflow_process` `DESTRUCTIVE`**

In `orchestrator/core/api/api_v1/endpoints/processes.py`, change the abort route decorator:

```python
@router.put(
    "/{process_id}/abort",
    response_model=None,
    status_code=HTTPStatus.NO_CONTENT,
    tags=[AgentTag.EXPOSED, AgentTag.DESTRUCTIVE],
    operation_id="abort_workflow_process",
)
```

- [ ] **Step 7: Run the annotation tests**

Run: `uv run --extra mcp pytest test/unit_tests/mcp/test_mcp.py -v`
Expected: PASS (all parametrized annotation cases + title/openWorld test + the existing 11-tool membership test).

- [ ] **Step 8: Commit**

```bash
git add orchestrator/core/agent_tags.py orchestrator/core/mcp/server.py \
    orchestrator/core/api/api_v1/endpoints/mcp_tools.py \
    orchestrator/core/api/api_v1/endpoints/processes.py \
    test/unit_tests/mcp/test_mcp.py
git commit -m "Stamp ToolAnnotations on MCP tools via method + AgentTag signals"
```

---

## Task 3: Expose the six curated GET endpoints as tools

**Files:**
- Modify: `products.py`, `product_blocks.py`, `resource_types.py`, `workflows.py`, `subscriptions.py`, `processes.py`
- Test: `test/unit_tests/mcp/test_mcp.py`

- [ ] **Step 1: Update the expected tool set and fixture (failing test first)**

In `test/unit_tests/mcp/test_mcp.py`, expand the imports, the expected set, and mount the extra routers.

Replace the current endpoints import line:

```python
from orchestrator.core.api.api_v1.endpoints import mcp_tools, processes, products
```
with the expanded list:

```python
from orchestrator.core.api.api_v1.endpoints import (
    mcp_tools,
    processes,
    product_blocks,
    products,
    resource_types,
    subscriptions,
    workflows,
)
```

Extend `EXPECTED_TOOL_NAMES` with the six new names:

```python
    "get_product",  # GET /api/products/{product_id}
    "get_product_block",  # GET /api/product_blocks/{product_block_id}
    "get_resource_type",  # GET /api/resource_types/{resource_type_id}
    "get_workflow_by_id",  # GET /api/workflows/{workflow_id}
    "get_subscription_domain_model",  # GET /api/subscriptions/domain-model/{subscription_id}
    "get_process_status_counts",  # GET /api/processes/status-counts
```

Mount the additional routers in the `app_with_agent_routes` fixture (after the existing three `include_router` calls):

```python
    app.include_router(workflows.router, prefix="/api/workflows")
    app.include_router(product_blocks.router, prefix="/api/product_blocks")
    app.include_router(resource_types.router, prefix="/api/resource_types")
    app.include_router(subscriptions.router, prefix="/api/subscriptions")
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run --extra mcp pytest test/unit_tests/mcp/test_mcp.py::test_all_expected_routes_carry_agent_tag -v`
Expected: FAIL — the six new `operation_id`s are missing from the route table.

- [ ] **Step 3: Tag `GET /products/{product_id}`**

In `orchestrator/core/api/api_v1/endpoints/products.py` (AgentTag is already imported), change:

```python
@router.get(
    "/{product_id}",
    response_model=ProductSchema,
    tags=[AgentTag.EXPOSED],
    operation_id="get_product",
)
def product_by_id(product_id: UUID) -> ProductTable:
    """Get a single product by id, including fixed inputs, product blocks and workflows.

    Use after ``list_products`` to inspect one product's full definition.
    """
    product = _product_by_id(product_id)
    if not product:
        raise_status(HTTPStatus.NOT_FOUND, f"Product id {product_id} not found")
    return product
```

- [ ] **Step 4: Tag `GET /product_blocks/{product_block_id}`**

In `orchestrator/core/api/api_v1/endpoints/product_blocks.py`, add the import under the existing imports:

```python
from orchestrator.core.agent_tags import AgentTag
```

and change the GET route:

```python
@router.get(
    "/{product_block_id}",
    response_model=ProductBlockSchema,
    tags=[AgentTag.EXPOSED],
    operation_id="get_product_block",
)
def get_product_block_description(product_block_id: UUID) -> str:
    """Get a single product block definition by id, including its resource types."""
    product_block = db.session.get(ProductBlockTable, product_block_id)
    if product_block is None:
        raise_status(HTTPStatus.NOT_FOUND)
    return product_block
```

- [ ] **Step 5: Tag `GET /resource_types/{resource_type_id}`**

In `orchestrator/core/api/api_v1/endpoints/resource_types.py`, add the import:

```python
from orchestrator.core.agent_tags import AgentTag
```

and change the GET route:

```python
@router.get(
    "/{resource_type_id}",
    response_model=ResourceTypeSchema,
    tags=[AgentTag.EXPOSED],
    operation_id="get_resource_type",
)
def get_resource_type_description(resource_type_id: UUID) -> str:
    """Get a single resource type definition by id."""
    resource_type = db.session.get(ResourceTypeTable, resource_type_id)
    if resource_type is None:
        raise_status(HTTPStatus.NOT_FOUND)
    return resource_type
```

- [ ] **Step 6: Tag `GET /workflows/{workflow_id}`**

In `orchestrator/core/api/api_v1/endpoints/workflows.py`, add the import:

```python
from orchestrator.core.agent_tags import AgentTag
```

and change the GET route:

```python
@router.get(
    "/{workflow_id}",
    response_model=WorkflowSchema,
    tags=[AgentTag.EXPOSED],
    operation_id="get_workflow_by_id",
)
def get_workflow_description(workflow_id: UUID) -> str:
    """Get a single workflow definition by id (name, target, description, steps)."""
    workflow = db.session.get(WorkflowTable, workflow_id)
    if workflow is None:
        raise_status(HTTPStatus.NOT_FOUND)
    return workflow
```

- [ ] **Step 7: Tag `GET /subscriptions/domain-model/{subscription_id}`**

In `orchestrator/core/api/api_v1/endpoints/subscriptions.py`, add the import (if absent):

```python
from orchestrator.core.agent_tags import AgentTag
```

Change the route decorator and add a docstring as the first statement of the function:

```python
@router.get(
    "/domain-model/{subscription_id}",
    response_model=SubscriptionDomainModelSchema | None,
    tags=[AgentTag.EXPOSED, AgentTag.LARGE],
    operation_id="get_subscription_domain_model",
)
async def subscription_details_by_id_with_domain_model(
    request: Request, subscription_id: UUID, response: Response, filter_owner_relations: bool = True
) -> dict[str, Any] | None:
    """Get a subscription's full domain model: the nested product-block tree and relations.

    LARGE: returns the entire instantiated product-block tree. Prefer
    ``get_subscription_details`` for a flat header; use this only when the full
    tree is required.
    """
    def _build_response(model: dict, etag: str) -> dict[str, Any] | None:
```

(Leave the rest of the function body unchanged.)

- [ ] **Step 8: Tag `GET /processes/status-counts`**

In `orchestrator/core/api/api_v1/endpoints/processes.py` (AgentTag already imported), change:

```python
@router.get(
    "/status-counts",
    response_model=ProcessStatusCounts,
    tags=[AgentTag.EXPOSED],
    operation_id="get_process_status_counts",
)
def status_counts() -> ProcessStatusCounts:
    """Get aggregate counts of processes and tasks grouped by status.

    Cheap dashboard-style summary; use before listing to gauge system state.
    """
    stmt = (
        select(ProcessTable)
        .with_only_columns(ProcessTable.is_task, ProcessTable.last_status, count(ProcessTable.last_status))
        .group_by(ProcessTable.is_task, ProcessTable.last_status)
    )
    rows = db.session.execute(stmt).all()
    return ProcessStatusCounts(
        process_counts={status: num_processes for is_task, status, num_processes in rows if not is_task},
        task_counts={status: num_processes for is_task, status, num_processes in rows if is_task},
    )
```

- [ ] **Step 9: Extend the annotation test with a GET case**

In `test/unit_tests/mcp/test_mcp.py`, add a parametrize case to `test_tool_annotations`:

```python
        pytest.param("get_product", True, True, False, id="readonly-get-by-id"),
```

- [ ] **Step 10: Run the full MCP test module**

Run: `uv run --extra mcp pytest test/unit_tests/mcp/test_mcp.py -v`
Expected: PASS — 17 tools present; all annotation cases green.

- [ ] **Step 11: Commit**

```bash
git add orchestrator/core/api/api_v1/endpoints/products.py \
    orchestrator/core/api/api_v1/endpoints/product_blocks.py \
    orchestrator/core/api/api_v1/endpoints/resource_types.py \
    orchestrator/core/api/api_v1/endpoints/workflows.py \
    orchestrator/core/api/api_v1/endpoints/subscriptions.py \
    orchestrator/core/api/api_v1/endpoints/processes.py \
    test/unit_tests/mcp/test_mcp.py
git commit -m "Expose curated GET endpoints (product, block, resource type, workflow, subscription domain-model, process status-counts) as MCP tools"
```

---

## Task 4: Add the docstring guardrail test

**Files:**
- Test: `test/unit_tests/mcp/test_mcp.py`

- [ ] **Step 1: Add the guardrail test**

Append to `test/unit_tests/mcp/test_mcp.py`:

```python
def test_exposed_routes_have_docstrings(app_with_agent_routes: FastAPI) -> None:
    """Every agent-exposed route has a non-empty docstring (its MCP tool description)."""
    missing = [
        getattr(route, "path", "")
        for route in app_with_agent_routes.routes
        if (AgentTag.EXPOSED.value in (getattr(route, "tags", None) or []))
        and not ((getattr(getattr(route, "endpoint", None), "__doc__", "") or "").strip())
    ]
    assert not missing, f"agent-exposed routes missing a docstring: {missing}"
```

- [ ] **Step 2: Run it**

Run: `uv run --extra mcp pytest test/unit_tests/mcp/test_mcp.py::test_exposed_routes_have_docstrings -v`
Expected: PASS (Tasks 2–3 gave every exposed route a docstring).

- [ ] **Step 3: Commit**

```bash
git add test/unit_tests/mcp/test_mcp.py
git commit -m "Add guardrail test: every agent-exposed route must have a docstring"
```

---

## Task 5: Update the MCP documentation

**Files:**
- Modify: `docs/reference-docs/mcp.md`

- [ ] **Step 1: Add the new tools to the tool table**

In `docs/reference-docs/mcp.md`, append rows to the "default toolset" table:

```markdown
| `get_product`                             | Get one product definition by id                    |
| `get_product_block`                       | Get one product block definition by id              |
| `get_resource_type`                       | Get one resource type definition by id              |
| `get_workflow_by_id`                      | Get one workflow definition by id                   |
| `get_subscription_domain_model`           | Get a subscription's full product-block tree (large)|
| `get_process_status_counts`               | Aggregate process/task counts grouped by status     |
```

- [ ] **Step 2: Document annotations + new tags**

Add a new section after "Extending":

```markdown
## Tool annotations

Every generated tool carries [MCP `ToolAnnotations`](https://modelcontextprotocol.io/)
so clients can reason about safety (e.g. auto-approve reads):

* `readOnlyHint` — `GET` routes, or any route tagged `AgentTag.READONLY`.
* `idempotentHint` — read-only routes, or `PUT`/`DELETE`.
* `destructiveHint` — `DELETE` routes, or any route tagged `AgentTag.DESTRUCTIVE`.
* `openWorldHint` — always `False` (the orchestrator acts on its own database).
* `title` — a humanized form of the `operation_id`.

Because the curated read tools in `mcp_tools.py` are `POST` routes, tag them
`AgentTag.READONLY` so they are correctly marked safe. Tag irreversible
mutations (e.g. `abort_workflow_process`) `AgentTag.DESTRUCTIVE`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/reference-docs/mcp.md
git commit -m "Document MCP tool annotations and the new GET-derived tools"
```

---

## Task 6: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the MCP tests, type check, and lint**

Run:
```bash
uv run --extra mcp pytest test/unit_tests/mcp/test_mcp.py -v
uv run mypy orchestrator/core/mcp/server.py orchestrator/core/agent_tags.py
uv run ruff check orchestrator/core/mcp orchestrator/core/api/api_v1/endpoints
uv run ruff format --check orchestrator/core/mcp orchestrator/core/api/api_v1/endpoints
```
Expected: all PASS / no findings.

- [ ] **Step 2: Sanity-check the broader endpoint test suites still pass**

Run: `uv run pytest test/unit_tests/api -q`
Expected: PASS (the route edits only add `operation_id`/tags/docstrings; no behavior change).

---

## Self-Review

**Spec coverage:**
- Annotation policy (readOnly/idempotent/destructive/openWorld/title) → Task 2. ✓
- New `AgentTag.READONLY`/`DESTRUCTIVE` → Task 2 steps 3,5,6. ✓
- Six curated GET endpoints as tools → Task 3. ✓
- Correctness tags on existing curated tools (READONLY ×7, DESTRUCTIVE on abort) → Task 2 steps 5–6. ✓
- Excluded noise GETs → enforced by exact-set equality in `test_all_expected_routes_carry_agent_tag` (Task 3). ✓
- Tests: membership (17), parametrized annotations, docstring guardrail → Tasks 2–4. ✓
- Tight input schemas ("function annotations") → all six routes already type path params as `UUID`; no untyped params introduced. ✓
- Payload note (domain-model LARGE, not trimmed) → Task 3 step 7 (LARGE tag + docstring warning). ✓
- Docs → Task 5. ✓
- Tool-vs-Resource = Tools only → `route_maps` unchanged (EXPOSED→TOOL). ✓

**Placeholder scan:** none — every code/test step contains complete content.

**Type/name consistency:** `build_mcp`, `_annotate`, `_humanize` consistent across Task 1/2 and tests; `operation_id`s (`get_product`, `get_product_block`, `get_resource_type`, `get_workflow_by_id`, `get_subscription_domain_model`, `get_process_status_counts`) consistent between route edits (Task 3) and `EXPECTED_TOOL_NAMES`/parametrize ids. All six are unique across the app.
