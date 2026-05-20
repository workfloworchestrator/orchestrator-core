# What's new in orchestrator-core since 4.0

A tour of the major capabilities added across the 4.x line and into 5.0.

- Audience: mixed — operators, developers, and stakeholders
- Timeline: 4.0 (mid-2025) through 5.0.1 (May 2026)
- Roughly 35 releases, ~530 commits, six big themes

::: notes
The 4.x line was a long arc — about a year of work between 4.0 and 5.0. Rather
than walk through 35 changelogs, we'll group the work into six themes that
each shaped what the platform can do today: AI search, AI agents,
authorization, scheduling, workflow capabilities, and developer experience.
:::

# Agenda

1. The 4.x story at a glance
2. **AI-powered search** (4.5 → 5.0)
3. **AI agent platform** (4.8 → 5.0)
4. **Authorization framework** (4.1 → 4.8)
5. **Scheduler rebuilt** (4.4)
6. **Workflow features**: reconcile + run predicates
7. **Observability & ops**
8. **GraphQL evolution**
9. **Extensibility** (5.0)
10. **Developer experience**
11. Where to dig deeper

# The 4.x story at a glance

- **Bigger surface area** — the platform grew from "workflow engine + GraphQL" into a full orchestration suite
- Three new pillars added: **search**, **AI agents**, and **fine-grained auth**
- Existing pillars matured: scheduler, observability, GraphQL, extensibility
- Theme of the era: **expose orchestrator-core to other systems** — UIs, AI tooling, external services

::: notes
If you had to describe the 4.x arc in one sentence: orchestrator-core stopped
being just a backend for a single UI and became a platform that other things
talk to. That shows up in nearly every new feature — search exposes a query
API, the agent platform exposes MCP and A2A, the auth framework lets external
systems contribute decisions, and the namespace change opens the door to
optional add-on modules.
:::

# AI-powered search (4.5 → 5.0)

- Started as an opt-in `[search]` extra in 4.5 with LLM-assisted retrieval
- Structured search added in 4.8 with aggregations, sorting, totals
- A dedicated `/api/search` endpoint replaces TSV-style `query=` parameters
- Indexes subscriptions, products, processes, **and** workflows
- **Now mandatory in 5.0** — `litellm` is a core dependency; vector + text always on
- Powered by pgvector + standard PostgreSQL extensions

::: notes
Search began life in 4.5 as a proof of concept and steadily hardened across
4.6, 4.7, and 4.8 — coverage jumped from 59% to 92% along the way. In 5.0 the
team committed and made it part of the core, on the bet that everyone will
benefit. Text search works out of the box; semantic search activates when
you configure an embedding provider. For operators, the deployment story is
simple: pgvector image, five PostgreSQL extensions, and a CLI command to
populate the index.
:::

# AI agent platform (4.8 → 5.0)

- Foundations laid in 4.5 (schema retrieval, validation exceptions, auth-aware router)
- 4.8 introduced a **finite-state-machine agent** with skills, planners, and tool artifacts
- Transport adapters: **AG-UI** for streaming UIs, **A2A** with agent card at `/.well-known/agent-card.json`
- **MCP server** in 5.0 mounted at `/mcp` (opt-in via `fastmcp` install)
- All endpoints share the platform's auth via `AgentAuthMiddleware`

::: notes
This is the platform's bet on AI-native operations. The agent runtime is a
cyclic finite-state machine — it plans, acts, observes, and iterates — and
the surrounding scaffolding makes it pluggable across three industry
protocols. AG-UI for interactive chat-like flows, A2A for agent-to-agent
delegation, and MCP for tool integration from clients like Claude or Cursor.
None of it bypasses your existing OIDC setup; the same authorization rules
that protect workflows protect agent actions.
:::

# Authorization framework (4.1 → 4.8)

- 4.1: RBAC for running, resuming, retrying workflows
- 4.2: `isAllowed` field in GraphQL queries — UIs can hide what users can't do
- 4.6: `retry_auth_callback` on step / retrystep / step_group
- 4.7: **Async authorization callbacks**, global default authorizers
- 4.8: `AgentAuthMiddleware` for A2A and MCP endpoints
- 5.0: Callbacks now receive a rich `AuthContext` (user + action + workflow + step)

::: notes
Authorization started in 4.1 as a small set of RBAC decorators on workflow
lifecycle endpoints and evolved into a comprehensive framework. The
`isAllowed` field is a small thing with big UX consequences — the UI can grey
out actions instead of letting the user click and fail. The 5.0 `AuthContext`
gives callbacks the full picture of who is trying to do what to which
workflow at which step, so you can write much smarter policies — e.g.
"engineer can retry their own steps but not approve them."
:::

# Scheduler rebuilt with APScheduler (4.4)

- 4.4: Replaced the built-in scheduler with **APScheduler** and a persistent jobstore
- Schedules survive restarts; jobs visible in `apscheduler_jobs`
- 4.7: Full **Scheduler CRUD API** — schedule via UI or HTTP, not just code
- 4.7: Decorator-based scheduling deprecated; default schedules removed
- 4.8: `validate-products` migrated to API + **run predicates**
- `python main.py scheduler load-initial-schedule` restores defaults

::: notes
Before 4.4, scheduling was decorator-only — fine for fixed jobs, painful for
anything dynamic. APScheduler brings persistence and the new CRUD API lets
users schedule jobs from the UI, the API, or both. The path from 4.4 through
4.8 deprecates decorator scheduling step by step; by 5.0 the GraphQL
`scheduledTasks` query only shows API-scheduled jobs. If you still rely on
decorators, the upgrade guide walks you through migrating them.
:::

# Workflow features

- **Reconcile workflow decorator** (4.4) — sync subscriptions with external systems
- Reconcile target + lifecycle validation in workflow steps (4.5)
- **Workflow run predicates** (4.8) — declarative conditions on whether a workflow may start
- Validation report endpoint with `lastValidatedAt` on subscriptions (4.3)
- Resume CREATED/RESUMED processes correctly (4.3)
- Improved step timestamping (4.2) and structlog context per step (3.2)

::: notes
Two big additions and a handful of refinements. Reconcile workflows formalize
the "make external state match our state" pattern — useful when you sync to
an IPAM, a CMDB, or another orchestrator. Run predicates are about gating:
think maintenance mode, dependency checks, or "this workflow can't run while
that other one is in progress." Together they let you express more of the
operational logic declaratively rather than in step code.
:::

# Observability & operations

- **Metrics endpoint** (4.0) with example **Grafana dashboard** (4.2) shipped in the repo
- **Worker status monitor** (4.8) — live count of running processes, replaces brittle counter column
- Validation report endpoint with `lastValidatedAt` per subscription (4.3)
- Distributed lock manager added with test coverage
- Migrations now logged with truncated tracebacks instead of full dumps (4.8)
- MkDocs CI made strict — docs build is part of the test suite (4.3, 4.6)

::: notes
Observability got steady, unflashy attention across 4.x. The Grafana
dashboard JSON ships in the repo as a starting point. The worker status
monitor replaces a counter column that had to be manually incremented on
every process start and stop — error-prone and a source of drift. The
validation report endpoint lets operators see, at a glance, which
subscriptions have been validated recently and which haven't.
:::

# GraphQL evolution

- 4.2: `isAllowed` on workflow query, `workflow_target` on `ProcessSubscriptionTable` deprecated
- 4.3: Async resolver wrapping via `make_async` + `run_in_threadpool`
- 4.6: Int-type-redefinition fix; fetching soft-deleted workflows fixed
- 4.7: `get_current_user` properly awaited in resolvers
- 5.0: Strawberry upgraded with `FEDERATION_VERSION`, multi-UI support (`graphiql` / `apollo-sandbox` / `pathfinder`)
- 5.0: Custom scalars use `name=` (cleaner than the old `NewType` pattern)

::: notes
GraphQL itself didn't get a headline rewrite, but the implementation got a
lot more solid. The async resolver wrapper means slow synchronous code in a
resolver doesn't block the entire event loop. Federation support, soft-delete
correctness, and authorization fields all matured. By 5.0 the layer is stable
enough that the team felt confident pulling Strawberry up to a current
release with the breaking changes that came with it.
:::

# Extensibility — the 5.0 unlock

- orchestrator-core is now a **namespace package** (`orchestrator.core.*`)
- Opens the door to optional add-on modules built and shipped separately
- New **`OrchestratorCore.register_table()`** API to extend base tables (e.g. `SubscriptionTable`) with computed columns
- Result: customize and extend without forking or monkey-patching
- Background: `docs/architecture/extensibility/packaging.md`

::: notes
The namespace move in 5.0 is the structural change that unlocks the next
phase of the project. Before, customizing core models meant subclassing and
hoping nothing else imported the original; now `register_table()` lets you
attach extra column properties cleanly, visible to both SQLAlchemy and
GraphQL. The namespace itself means add-on modules — think of optional
features like search, agents, billing integrations — can live in their own
packages and compose with the core.
:::

# Developer experience

- **Build tooling**: flit → **uv** in 4.2; `uv_build` for wheels in 5.0
- **Linting**: scattered black usage fully replaced by **ruff**
- **Python 3.14** support enabled in 4.6
- **Renovate** replaced Dependabot (4.6) — better grouping, lower noise
- **Mypy 1.9 → 1.19** in 5.0 — roughly 2× faster type checking
- **Vulture** added for dead-code detection
- Test coverage climbed dramatically — search 59→92%, websocket 67→99%, CLI 20→80%, API 42→76%

::: notes
None of these are user-facing, but together they're why the project moves as
quickly as it does. The uv migration speeds up installs and CI; the mypy
upgrade makes the test loop tighter; Renovate keeps dependencies fresh
without drowning maintainers in PRs. The coverage jump matters too — by 5.0
most of the codebase has tests behind it, which is why the team felt
confident about the 5.0 breaking changes.
:::

# Where to dig deeper

- **Upgrade guides** — `docs/guides/upgrading/{4.7,4.8,5.0}.md`
- **Architecture** — `docs/architecture/` (extensibility, application, orchestration)
- **Search reference** — `docs/reference-docs/search.md`
- **Tasks / scheduler** — `docs/guides/tasks.md`
- **Run predicates** — `docs/reference-docs/workflows/run-predicates.md`
- **Releases** — GitHub releases page, tags `4.0.0` through `5.0.1`
- **Q&A**

::: notes
The upgrade guides are surprisingly readable as feature overviews — they
explain not just what to change but why each change exists. The architecture
docs are where to go for the bigger picture, especially the extensibility
section that motivates the namespace move. Questions?
:::
