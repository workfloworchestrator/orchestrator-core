# MCP Server: Tool-Surface Quality + Curated GET Endpoints

**Date:** 2026-05-29
**Status:** Approved (design)

## Problem

The MCP server (`orchestrator/core/mcp/server.py`) auto-generates tools from FastAPI
routes tagged `AgentTag.EXPOSED` via `FastMCP.from_fastapi(...)`. Two issues:

1. **Tool-surface quality is unoptimized.** No `ToolAnnotations` are emitted, so an
   MCP client cannot tell a read from a write, cannot auto-approve safe reads, and
   gets no human-readable titles. Worse, the curated read tools in `mcp_tools.py`
   are **POST** routes (`search_subscriptions`, `list_workflows`, `get_*`), so any
   method-based heuristic on the client side classifies them as state-mutating.

2. **Coverage gap.** Several useful GET lookups (`products/{id}`,
   `product_blocks/{id}`, `resource_types/{id}`, `workflows/{id}`, subscription
   domain-model, process status-counts) are not exposed as tools at all.

These pull in opposite directions: naively exposing *every* GET would add
operational noise (health, translations, UI typeahead) and bloat the agent's
context, hurting tool-selection accuracy. The goal is **more coverage without
degrading selection** — weighted toward LLM tool-selection/context quality, while
addressing payload size where it overlaps.

## Decisions (locked during brainstorming)

- **Performance target:** both runtime and selection, **weighted to selection**
  (annotations, clean names/titles, sharp descriptions, tight schemas).
- **GET scope:** a **curated agent-relevant subset**, not all GETs. Operational/UI
  noise stays excluded.
- **Tool vs Resource:** expose everything as **Tools** for maximum MCP-client
  compatibility (current behavior preserved).
- **Strategy:** in-place tagging of existing GET routes + a single centralized
  annotation hook (chosen over duplicate curated wrappers and over method-only
  inference).

## Architecture

No change to the mount/auth/transport flow. Two kinds of change:

1. **`server.py`** — pass a `mcp_component_fn` (`_annotate`) to
   `FastMCP.from_fastapi(...)`. Extract the `route_maps` list and `_annotate` to
   module level so tests build the MCP from the *real* configuration rather than a
   re-implementation.
2. **Route metadata** — add `operation_id`, a docstring, and `AgentTag`s to the
   curated GET routes; add correctness tags to existing curated tools.

Annotations are computed once at server-build time — **zero per-call runtime cost**.

```
MCP client → /mcp → fastmcp (route_maps + _annotate) → in-process httpx
            (auth header forwarded) → FastAPI route → Depends(authorize)
```

## Components

### `AgentTag` additions (`orchestrator/core/agent_tags.py`)

```python
EXPOSED = "agent-exposed"
LARGE = "agent-large"
READONLY = "agent-readonly"        # non-GET route that does NOT mutate state
DESTRUCTIVE = "agent-destructive"  # irreversible mutation (abort, delete)
```

### Annotation hook (`server.py`)

`_annotate(route, component)` sets `ToolAnnotations` on every generated
`OpenAPITool`. It is defensive: only mutates `OpenAPITool` instances and tolerates a
missing `tags`/`method`.

| `ToolAnnotations` field | Rule |
|---|---|
| `readOnlyHint` | `method == "GET"` **or** `AgentTag.READONLY` present |
| `idempotentHint` | read-only **or** `method in {"PUT", "DELETE"}` |
| `destructiveHint` | `method == "DELETE"` **or** `AgentTag.DESTRUCTIVE` present |
| `openWorldHint` | `False` (orchestrator operates on its own DB) |
| `title` | humanized `component.name`, e.g. `get_process_status` → "Get Process Status" |

`route_maps` are unchanged in behavior (`EXPOSED → TOOL`, else `EXCLUDE`) but moved
to a module-level constant so the test suite reuses them.

### Curated GET endpoints to expose (all as Tools)

| Route | `operation_id` | tags |
|---|---|---|
| `GET /products/{product_id}` | `get_product` | EXPOSED |
| `GET /product_blocks/{product_block_id}` | `get_product_block` | EXPOSED |
| `GET /resource_types/{resource_type_id}` | `get_resource_type` | EXPOSED |
| `GET /workflows/{workflow_id}` | `get_workflow_by_id` | EXPOSED |
| `GET /subscriptions/domain-model/{subscription_id}` | `get_subscription_domain_model` | EXPOSED, LARGE |
| `GET /processes/status-counts` | `get_process_status_counts` | EXPOSED |

Each receives a concise, LLM-oriented docstring (first line: what it does; then when
to use it; size warning where `LARGE`). All path params are already typed (`UUID`),
so derived input schemas stay tight; each exposed route's signature is verified to be
fully typed.

### Correctness tags on existing curated tools

- `READONLY`: `list_workflows`, `get_workflow_form`,
  `get_subscription_available_workflows`, `get_process_status`,
  `list_recent_processes`, `get_subscription_details`, `search_subscriptions`.
- `DESTRUCTIVE`: `abort_workflow_process` (PUT).
- Unchanged (write, non-destructive): `create_workflow`, `resume_workflow_process`.
- `list_products` (GET) needs no tag — read-only is inferred from method.

### Excluded as noise (explicitly NOT exposed)

`health/`, `translations/{language}` (large i18n dict), `search/paths` +
`search/definitions` (UI typeahead), `settings/cache-names|worker-status|status|overview`,
subscription customer-descriptions, and the deprecated `subscriptions/workflows/{id}`.
Subscription search/details and process status/list are already covered by existing
curated tools.

## Payload / latency

Only `get_subscription_domain_model` returns a large tree; it is flagged `LARGE` so
clients warn the agent to narrow first. Its schema is **not** trimmed in v1 — the flat
`get_subscription_details` already serves the cheap case. Future optional lever
(not done now): drop `output_schema` on the largest tools to reduce context cost.

## Error handling

- Exposed GETs already `raise_status(404, ...)`; this propagates through the existing
  exception chain to the MCP client as a tool error. No change.
- `_annotate` never raises on unexpected component types or missing attributes.

## Testing (`test/unit_tests/mcp/test_mcp.py`)

- Mount the additional routers (`workflows`, `product_blocks`, `resource_types`,
  `subscriptions`) in the fixture; build the MCP via the shared config (real
  `route_maps` + `_annotate`).
- Update `EXPECTED_TOOL_NAMES` (11 → 17). Exact-set equality already guarantees the
  excluded noise GETs do not leak in.
- **Guardrail/lint test:** every `EXPOSED` route has a non-empty `operation_id`
  **and** a non-empty docstring.
- **Parametrized annotation test** (`pytest.param(..., id=...)`):
  - `get_product` → `readOnlyHint True`
  - `search_subscriptions` (POST + READONLY) → `readOnlyHint True`
  - `create_workflow` (POST) → `readOnlyHint False`
  - `resume_workflow_process` (PUT) → `idempotentHint True`, `readOnlyHint False`
  - `abort_workflow_process` (PUT + DESTRUCTIVE) → `destructiveHint True`
  - all tools → `openWorldHint False`, non-empty `title`

## Docs

Update `docs/reference-docs/mcp.md`: add the 6 new tools to the tool table, and
document the new `AgentTag`s and the annotation-inference rules.

## Out of scope

- Exposing GETs as MCP Resources / Resource Templates (kept as Tools).
- Trimming the `subscription_domain_model` payload/schema.
- Exposing operational/UI GET endpoints.
- Any change to the auth-forwarding or transport mechanism.
