# orchestrator-core 5.0

What operators need to know

- 5.0.0 released 2026-05-12
- 5.0.1 hotfix released 2026-05-18 — use this one
- A short walk through the breaking changes and headline features

::: notes
Welcome. In the next 15 minutes I will walk through what changed between 4.0
and 5.0, weighted toward what you need to do as an operator. Two release dates
matter: 5.0.0 went out on May 12, and 5.0.1 followed six days later with
important scheduler fixes — please upgrade straight to 5.0.1, not 5.0.0.
:::

# Agenda

- Prerequisites — 4.7 and 4.8 changes you may have skipped
- The 12 breaking changes in 5.0
- Three new features worth knowing about
- A concrete operator upgrade checklist
- Q&A

::: notes
We start with two short prerequisite slides because the 5.0 upgrade guide
explicitly says: if you skipped 4.7 or 4.8, read those first. Then we go
through the breaking changes — grouped so we can move quickly — then features,
then a checklist you can take back to your runbook.
:::

# 5.0 at a glance

- One **headline** change: orchestrator is now a namespace package
- 12 breaking changes total — most are mechanical find-and-replace
- 3 new operator-visible features: LLM search, MCP server, `register_table()`
- A migration helper script ships with the release
- Authoritative source: `docs/guides/upgrading/5.0.md`

::: notes
The single change that touches every line of your code is the namespace move.
Everything else is smaller in scope. The team ships a `migrate_50` script that
rewrites your imports automatically, so even the big change is mostly
mechanical. The upgrade guide in the repo is the source of truth for this
talk — every claim here points back to a numbered section in that file.
:::

# First: prerequisites from 4.7 and 4.8

- **4.7**: scheduling via `@scheduler.scheduled_job` is **deprecated** — use the Scheduler API
- **4.7**: workflow authorization callbacks must now be `async def`
- **4.8**: `validate-products` schedule moved from decorator to the API
- **4.8**: workflow **run predicates** introduced (gate workflows on conditions)
- To restore default schedules: `python main.py scheduler load-initial-schedule`

::: notes
If your last upgrade was 4.6 or earlier, read the 4.7 and 4.8 upgrade guides
before 5.0. The decorator-based scheduling was deprecated in 4.7 and is on its
way out — 5.0 already changes how the GraphQL `scheduledTasks` query reports
them. If you have custom workflow auth callbacks, they must be `async def` from
4.7 onward. The `load-initial-schedule` command brings back the default jobs
through the API if you want them.
:::

# Breaking #1 — Namespace package

- Every `orchestrator.*` import becomes `orchestrator.core.*`
- Automated rewrite: `uv run -m orchestrator.core.devtools.scripts.migrate_50 <dir>`
- Run it against your project code **and** your tests
- Build tooling changed: `flit` → `uv_build`, `black` → `ruff`
- Motivation: future optional add-on modules — see `docs/architecture/extensibility/packaging.md`

::: notes
This is the change that ripples through everything you've written against
orchestrator-core. The good news is the team ships a migration script that
rewrites imports for you — point it at your source tree and your tests. Don't
forget patches in tests, Strawberry `lazy("...")` references, and Celery
`include=[...]` lists — those are string literals the linter won't catch. The
build tooling switch (flit/black to uv_build/ruff) only matters if you
contribute upstream.
:::

# Breaking #2 — Scheduled tasks need a DB migration

- APScheduler stores the **pickled module path** of every job
- The namespace change invalidates those paths — jobs would silently disappear
- Migration `cab8b6a0ac92` rewrites the stored paths automatically
- **Order matters**: stop scheduler → back up `apscheduler_jobs` → `python main.py db upgrade heads`
- Use **5.0.1**, not 5.0.0 — the fix landed in #1645

::: notes
This is the single most dangerous part of the upgrade, and the reason 5.0.1
exists. APScheduler pickles the fully qualified function name into the
database, so when the namespace shifts those references break and the
scheduler silently skips them. The migration rewrites them, but only if the
scheduler isn't running and overwriting the corrections. Stop scheduler,
back up the table with a CREATE TABLE AS, run `db upgrade heads`, then start
the scheduler. The restore SQL is in the upgrade guide if anything goes
sideways.
:::

# Breaking #3 — psycopg2 → psycopg3

- Dialect change in **every** `DATABASE_URI`:
  - `postgresql://...` → `postgresql+psycopg://...`
- Update `.env`, CI configs, deploy scripts, Helm values
- Dependency: `psycopg[binary]>=3.3.3` (was `psycopg2-binary`)
- **Autobegin**: psycopg3 starts a transaction on first query — wrap loose queries in `transactional()`
- Deprecation warning at startup if old dialect is detected

::: notes
The dialect change is mechanical but easy to miss because it lives in your
environment, not your code. Audit every place a Postgres URI lives — including
test databases, CI, and Helm values. Direct uses of psycopg2 should be ported
to psycopg3; the API is close but not identical. The subtler issue is
autobegin: psycopg3 implicitly opens a transaction on the first query, so any
query outside a `transactional()` context can leave a connection idle in
transaction. The framework handles its own paths, but custom Celery handlers
or workflow steps that hit the DB directly need wrapping.
:::

# Breaking #4 — Secret settings for URIs

- `DATABASE_URI`: `PostgresDsn` → `SecretPostgresDsn`
- `CACHE_URI`: `RedisDsn` → `SecretRedisDsn`
- `WEBSOCKET_BROADCASTER_URL`: `str` → `SecretStr`
- Values are now auto-masked in logs, prints, and tracebacks
- Call `.get_secret_value()` everywhere you read these settings
- **Critical**: patch your `migrations/env.py` — Alembic needs the unwrapped DSN

::: notes
These three settings can carry passwords, so 5.0 wraps them in Pydantic Secret
types. The values are masked when settings are logged, printed, or appear in
tracebacks — which is the whole point. Every read site needs
`.get_secret_value()`. The one that surprises people is the Alembic env.py,
because it sets `sqlalchemy.url` from `DATABASE_URI` — if you skip that line,
Alembic will try to connect to a literal `**********` and fail. The upgrade
guide shows the exact diff.
:::

# Breaking #5–8 — Forms and GraphQL

- `pydantic-forms` ≥ 2.4.0:
  - `ReadOnlyField()` → `read_only_field()` for scalars
  - `ReadOnlyField([...], default_type=list[...])` → `read_only_list([...])`
- `FEDERATION_ENABLED` (bool) → `FEDERATION_VERSION` (string, default `"2.9"`)
- `SERVE_GRAPHQL_UI` is now a string: `"graphiql" | "apollo-sandbox" | "pathfinder" | ""`
- Custom Strawberry scalars: replace `NewType("Foo", str)` with `name="Foo"`

::: notes
Four smaller changes grouped together. The pydantic-forms split exists because
the old API forced you to declare `default_type` for non-scalars; the new
typed factories make the intent clear. The Strawberry upgrade brings two env
var changes and a tweak to how custom scalars are declared — drop the
`NewType` wrapper, pass `name=` instead. None of these are large in scope,
but each is a hard error rather than a deprecation warning, so they're worth
calling out.
:::

# Breaking #9–12 — Auth and miscellaneous

- `authorize` and `authorize_websocket` now **raise 403 on `False`** (was silent)
- Workflow/step `Authorizer` callbacks receive `AuthContext`, not `OIDCUserModel`
  - Has `user`, `action`, `workflow`, `step` — richer auth decisions possible
- `engine_settings.running_processes` column removed (replaced by `WorkerStatusMonitor`)
  - Service rename: `get_engine_settings()` → `get_engine_settings_table()` (+ variants)
- Workflow decorator `description=` is **deprecated** — manage in DB / UI instead

::: notes
The auth change has a real failure mode: if your custom Authorization returns
False and you previously assumed it was silently allowing requests, those
requests will start 403'ing. So verify behavior, don't just verify the
signature. The callback signature change is straightforward — accept
`AuthContext` and pull `.user` from it; you also get the workflow and step
metadata for free. The engine_settings change is internal but visible if you
query that column directly — use the `/settings/status` REST endpoint or the
GraphQL `settings` query instead. The description deprecation is opt-in for
now; you'll get a warning, not an error.
:::

# New feature — LLM-powered search is the default

- No more `SEARCH_ENABLED`, no more `[search]` pip extra — `litellm` is core
- Required PostgreSQL extensions: `uuid-ossp`, `ltree`, `unaccent`, `pg_trgm`, **`vector`**
- `vector` needs **pgvector** — use `pgvector/pgvector:pg17` if you can
- Migration `262744958e0c` creates the AI search tables
- Index your data:

```bash
python main.py index subscriptions
python main.py index products
python main.py index processes
python main.py index workflows
```

- Env rename: `OPENAI_API_KEY` → `EMBEDDING_API_KEY`, `OPENAI_BASE_URL` → `EMBEDDING_API_BASE`

::: notes
What was an opt-in beta in 4.x is now part of the core. Text search works out
of the box; semantic vector search needs an embedding provider configured.
The biggest deployment change is the pgvector requirement — if your Postgres
image doesn't carry it, switch to the official pgvector image or install the
extension. The migration creates the search tables; the indexing CLI populates
them. Don't forget to remove the old `SEARCH_ENABLED` and `OPENAI_*` env vars
from your configs so future-you isn't confused.
:::

# New feature — MCP server for AI workflow ops

- Model Context Protocol endpoint mounted at `/mcp`
- Lets AI agents drive workflow operations through a standard protocol
- Activates **only** when the optional `fastmcp` package is installed
- OIDC-protected — same auth story as the rest of the API

::: notes
If you have no plans to expose orchestrator-core to AI tooling, this slide is
informational: the endpoint stays inert unless `fastmcp` is installed. If you
do want it, install the package, restart, and the route appears under `/mcp`
behind OIDC. The MCP protocol is the same standard Anthropic and others use
for tool integration, so any MCP-aware client can drive workflows from here.
:::

# New feature — `OrchestratorCore.register_table()`

- Register a subclass's `column_property` definitions onto a base table mapper
- Makes custom computed columns visible to **SQLAlchemy queries and GraphQL**
- Typical use: extend `SubscriptionTable` with a joined-in display name

```python
app = OrchestratorCore(...)
app.register_table(SubscriptionTable, MySubscriptionTable)
```

- Register at **both** app startup **and** in your Celery worker startup

::: notes
This is the cleanest way yet to extend the core models without monkey-patching.
Define a subclass with the extra column_property attributes, then register it
once at startup. The base table mapper gets the columns and GraphQL exposes
them automatically. The gotcha — and it is easy to miss — is that Celery
workers boot a separate process with their own mapper state, so register
again in your worker startup or your background tasks won't see the new
columns.
:::

# Operator upgrade checklist

1. Read `docs/guides/upgrading/5.0.md` end to end (and 4.7 / 4.8 if needed)
2. Run `migrate_50` against your code repos and tests
3. Update `DATABASE_URI` dialect to `postgresql+psycopg://` everywhere
4. Patch `migrations/env.py` to use `.get_secret_value()`
5. **Stop the scheduler**, back up `apscheduler_jobs`, run `db upgrade heads`
6. Verify scheduled tasks via `show-schedule` CLI; restart scheduler
7. Ensure pgvector + extensions exist; re-index search:
   `python main.py index {subscriptions,products,processes,workflows}`
8. Remove `SEARCH_ENABLED`, `OPENAI_API_KEY`, `OPENAI_BASE_URL` from env
9. Pin **5.0.1** (the scheduler hotfix release)

Resources: `docs/guides/upgrading/5.0.md` · GitHub releases tagged `5.0.0`, `5.0.1`

::: notes
This is the slide to screenshot for your runbook. The order matters — stop the
scheduler before the DB upgrade, not after, because a running scheduler with
the old code can overwrite the migration's corrections. Pin 5.0.1 not 5.0.0;
5.0.1 carries fixes for scheduled tasks, form input on the first page, and a
validation task session bug. Questions?
:::
