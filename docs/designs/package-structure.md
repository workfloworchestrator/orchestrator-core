---
# tutorial | how-to | reference | explanation | mixed
diataxis: mixed
reviewed: false
---

# Design: package structure of `orchestrator.core`
<!-- diataxis: mixed -->

Status: proposal, tracked in [#2123](https://github.com/workfloworchestrator/orchestrator-core/issues/2123). The
restructuring itself is planned for a future major release, together with a migration script.
Two parts take effect now, starting with the parallel steps feature (PR #1444):

- the `orchestrator/core/beta/` package, a permanent home for features that may still change incompatibly;
- the target layout below, which new code should already follow where it can do so without moving existing code.

## Context
<!-- diataxis: explanation -->

Below `orchestrator/core` there are 20 packages and 9 modules. Most of them are fine, but where a symbol lives is often
hard to predict:

- `services/` and `utils/` each hold three or four kinds of code. `services/` mixes use cases (process and
  subscription operations), execution infrastructure (Celery app setup, executors, thread pool, parallel branches) and
  monitoring. `utils/` mixes pure helpers with API code, domain logic and infrastructure.
- `services/processes.py` (1,150 lines) is a kitchen sink of its own: process lifecycle, callback handling, step
  persistence, log recovery, thread pool management and engine locking.
- `workflow.py` (2,370 lines) holds the workflow DSL, the step result types, the execution engine and, on this branch,
  the parallel engine.
- `types.py` mixes typing helpers with domain types.
- Several features are spread over many packages. Settings live in 5 places, scheduling in 4, MCP in 3. The legacy
  subscription search query language sits in `utils/`, `db/` and `api/`, next to an unrelated LLM `search/` package.
- `workflow.py` (the DSL) and `workflows/` (built-in workflows *and* the workflow registry) are easy to confuse.
- Dependencies run both ways. `services/processes.py` lazily imports the executors, which import `services/processes.py`.
  `services/processes.py` raises HTTP errors (`api.error_handling.raise_status`). Two `utils` modules
  (`fixed_inputs`, `get_subscription_dict`) import from `services`.

## Goals
<!-- diataxis: explanation -->

- A reader can predict where a symbol lives from what it does.
- Top-level packages are features. Only modules that must be importable from the package root stay top-level.
- The rules can be checked automatically, so the structure doesn't erode again.
- Users upgrade with a script and deprecation warnings, not by hand.
- Features that are still changing are clearly marked, both in code and in their import path.

## Principles
<!-- diataxis: explanation -->

1. **Features, not layers.** A top-level package is a feature (`processes`, `schedules`, `mcp`), or one of the few
   technical foundations (`db`, `utils`). A feature package contains its own operations, schemas and forms. The
   interfaces (`api`, `graphql`, `mcp`, `cli`) stay separate, because they span all features.
2. **`utils` is a leaf.** It holds use-case-agnostic helpers that import nothing from `orchestrator.core` except other
   `utils` modules.
3. **No framework code in operations.** Feature operations don't import FastAPI, Celery or Strawberry, and don't raise
   HTTP errors. They raise exceptions from `errors.py`, and the interface layers map those to HTTP or GraphQL errors.
4. **The workflow DSL and the execution engine are separate.** `workflow/` is what users write workflows with.
   `execution/` is what runs them. User code imports from `workflow/`; only core code imports from `execution/`.
5. **Dependencies point one way:** interfaces → features → `execution` → `workflow`, `domain`, `db` → `utils`.
6. **Unstable features live in `beta/`** (see [Beta features](#beta-features)).

## Beta features
<!-- diataxis: mixed -->

### Purpose
<!-- diataxis: explanation -->

Some features need real-world use before their API settles. Parallel steps are the first. Loop steps
([#1947](https://github.com/workfloworchestrator/orchestrator-core/issues/1947)) will likely be next. Marking these
only in the docs, as with the `{: .beta }` marker on workflow authorization, is easy to miss. An import path containing
`beta` can't be missed: users opt in knowingly, and a code search finds every place that relies on a beta feature.

### Rules
<!-- diataxis: reference -->

- **Location.** Every beta feature is a package `orchestrator/core/beta/<feature>/`. Its public API is what
  `beta/<feature>/__init__.py` exports. Everything else is internal.
- **Compatibility.** Beta APIs may change incompatibly in a minor release. Each such change is listed in the changelog
  and the upgrade guide of that release.
- **Not beta.** These can't be beta, because they are hard to undo. They follow the normal compatibility rules, even
  when they exist only for a beta feature:
  - database schema and migrations;
  - REST and GraphQL fields;
  - settings.

  Design them generically. For example, the fork step columns are named `branch_count`, `branches_completed` and
  `branch_kind`, not `parallel_*`, so loop steps can reuse them. Mention in their description that they serve a beta
  feature.
- **Dependencies.** Beta code may import stable code. Stable code doesn't import beta code, with one exception:
  wiring modules that register a beta feature with the framework, such as Celery task registration in
  `services/tasks.py`. Wiring imports are listed in the feature's `__init__.py` docstring. One beta feature may import
  another, but shared code should move to its own `beta/` package (see [Loop steps](#loop-steps)).
- **Internal layout.** A beta package is laid out the way it will graduate. Modules are named after their target
  location, so graduation is a move, not a rewrite.
- **Exports.** Beta APIs aren't re-exported from `orchestrator.core` or other stable modules.
- **Documentation.** Docs pages and sections about a beta feature get the `{: .beta }` marker and use the `beta` import
  path in examples.
- **No runtime warning.** Using a beta feature doesn't log or warn. The import path is the signal.
- **Tests.** Tests live in `test/unit_tests/beta/<feature>/` and `test/integration_tests/beta/<feature>/`.
- **Graduation.** In a minor release, the feature moves to its stable location, and `beta/<feature>` is removed in
  the same release. There is no shim and no deprecation period. The changelog and upgrade guide list the new import
  paths.
- **Removal.** A beta feature that is dropped is removed without a deprecation period, and listed in the changelog and
  upgrade guide.

### Parallel steps
<!-- diataxis: reference -->

The parallel steps code added by PR #1444 moves into `beta/parallel/` in that same PR. Nothing of it has been released,
so this costs users nothing.

```
orchestrator/core/beta/
├── __init__.py          policy summary (this section, short)
└── parallel/
    ├── __init__.py      public API: parallel, map_parallel
    ├── dsl.py           parallel, map_parallel, _make_parallel_step, reconstruct_branch   → workflow/parallel.py
    ├── branching.py     _create_fork_step, _update_fork_step, _make_branch_dblogstep,
    │                    _collect_branch_results, _succeeded_branch_indices, _worst_status → execution/branching/
    ├── engine.py        _exec_parallel_branches (executor selection)                       → execution/parallel/
    ├── threadpool.py    _run_branch, _run_threadpool_branches                              → execution/parallel/
    └── worker.py        _dispatch_worker_branches, run_worker_branch, _join_and_resume,
                         _resolve_branch_from_db, _find_parallel_step,
                         _atomic_increment_completed (from services/parallel.py)           → execution/parallel/
```

These stay in stable code because they are generic branching support or fall under "Not beta" above:

| Code | Location |
|---|---|
| `ProcessStepRelationTable`, the `branch_*` columns, migration `18a7c2676fd3` | `db/models.py`, `migrations/` |
| `branch_count`, `branch_kind`, `branches_completed`, `child_steps` fields | `schemas/process.py`, `graphql/schemas/process.py` |
| `BranchKind` | `workflow.py`, next to `StepStatus` |
| `_branch_child_step_ids`, `_main_log_steps`, `process_steps_loader`, the fork handling in `_get_current_step_to_update` | `services/processes.py` |
| child steps in `enrich_step_details` | `utils/enrich_process.py` |
| `PARALLEL_BRANCH_QUEUE`, `PARALLEL_BRANCH_WORKFLOW_QUEUE` | `settings.py` |
| `execute_parallel_branch*` task registration (wiring import) | `services/tasks.py` |

Other effects of the move:

- `parallel` is removed from `orchestrator.core.__all__`. Users import it as
  `from orchestrator.core.beta.parallel import parallel, map_parallel`.
- The import cycle between `workflow.py` and `services/parallel.py` disappears, along with the function-level imports
  that work around it.
- The integration tests in `test/integration_tests/test_parallel_*.py` move to `test/integration_tests/beta/parallel/`.
  That resolves their "move to the correct place" TODOs.

## Target layout
<!-- diataxis: mixed -->

### Overview
<!-- diataxis: reference -->

```
orchestrator/core/
├── __init__.py       public entry points (OrchestratorCore, app_settings, step, workflow, …)
├── app.py            OrchestratorCore
├── settings/         app_settings, llm_settings; exposed-settings registry. Import path unchanged
├── version.py
├── log_config.py
├── errors.py         exception classes shared by all packages
│
├── api/              REST routers, exception handlers, request helpers
├── graphql/          Strawberry schema
├── mcp/              MCP server and its schemas
├── cli/              CLI, code generators, docs generation
├── websocket/        websocket manager, process broadcasting
│
├── workflow/         DSL for writing workflows, step results, workflow registry
├── execution/        engine that runs workflows: executors, step persistence, recovery, branching
├── processes/        process lifecycle: create, start, resume, abort, callbacks, queries
├── subscriptions/    subscription operations and relations
├── catalog/          products, product blocks, resource types, fixed inputs, workflow table
├── schedules/        scheduler, schedule forms and schemas
├── search/           LLM search
├── metrics/          Prometheus collectors, Flower metrics
├── security/         authentication, authorization
├── builtins/         ready-made workflows, tasks, steps and predicates
├── beta/             features that may change incompatibly
│
├── domain/           subscription and product models
├── forms/            generic form building blocks, validators, translations
├── db/               SQLAlchemy models, filters, sorting, queries, legacy search query language
├── migrations/
├── distlock/
├── testing/          fixtures and asserts for downstream test suites
├── devtools/
└── utils/            leaf helpers
```

### Top-level modules
<!-- diataxis: reference -->

Only modules that users import from the package root, or that everything depends on, stay top-level.

| Module | Decision |
|---|---|
| `__init__.py`, `app.py`, `version.py`, `log_config.py`, `py.typed` | stay |
| `settings.py` | becomes the package `settings/`; `orchestrator.core.settings` keeps working. `services/settings_env_variables.py` and `utils/expose_settings.py` move into it as `settings/exposed.py` |
| `workflow.py` | becomes `workflow/` and `execution/`, see below |
| `types.py` | typing helpers (`is_union`, `is_of_type`, `get_origin_and_args`, …) → `utils/typing.py`; `SubscriptionLifecycle`, `SAFE_USED_BY_TRANSITIONS_FOR_STATUS`, `SI` → `domain/lifecycle.py`; `BroadcastFunc` → `websocket/` |
| `targets.py` | `workflow/targets.py` |
| `security.py` | `security/__init__.py`, joined by `utils/auth.py` |
| `exception_handlers.py` | `api/exception_handlers.py` |
| — | new `errors.py`, from `utils/errors.py` |

### Workflow package
<!-- diataxis: reference -->

`workflow/` is everything a user needs to define a workflow. Nothing in it runs a workflow.

| Module | Contents | From |
|---|---|---|
| `workflow/__init__.py` | re-exports the public DSL, so `from orchestrator.core.workflow import step` keeps working | `workflow.py` |
| `workflow/dsl.py` | `Step`, `StepList`, `make_step_function`, `step`, `retrystep`, `inputstep`, `step_group`, `conditional`, `callback_step`, `begin`, `done`, `init`, `abort`, `focussteps`, `steplens`, `workflow`, `make_workflow` | `workflow.py` |
| `workflow/process.py` | `Process`, `Success`, `Skipped`, `Suspend`, `Waiting`, `AwaitingCallback`, `Abort`, `Failed`, `Complete`, `StepStatus`, `ProcessStatus` | `workflow.py` |
| `workflow/state.py` | `inject_args`, `form_inject_args`, `extract`, `merge_state` | `utils/state.py`, `services/processes.py` |
| `workflow/targets.py`, `workflow/assignee.py` | `Target`, `Assignee` | `targets.py`, `config/assignee.py` |
| `workflow/predicates.py` | `RunPredicatePass`, `RunPredicateFail`, `PredicateContext` | `workflow.py` |
| `workflow/registry.py` | `LazyWorkflowInstance`, `ALL_WORKFLOWS`, `get_workflow`, `removed_workflow` | `workflows/__init__.py`, `workflows/removed_workflow.py` |

`config/` is removed. Its only content, `Assignee`, is a workflow concept, and a package named `config` next to
`settings` suggests configuration.

### Execution package
<!-- diataxis: mixed -->

`execution/` runs workflows. It answers "how does a step run, get stored, and resume", independent of who started the
process.

```
execution/
├── engine.py          ProcessStat, _exec_step, _exec_steps, runwf, abort_wf, process_stat_var       (workflow.py)
├── persistence.py     safe_logstep, _db_log_step, _get_current_step_to_update, _update_process,
│                      _db_log_process_ex, PROCESS_STEP_HANDLER                                     (services/processes.py)
├── recovery.py        load_process, _recoverwf, _restore_log, _main_log_steps, _branch_child_step_ids (services/processes.py)
├── engine_status.py   engine settings table, global lock, marshall_processes                       (services/settings.py, services/processes.py)
├── process/           runs a whole process
│   ├── __init__.py    ExecutorFunction, get_execution_context                                      (services/executors/types.py, services/processes.py)
│   ├── runner.py      _run_process_async (DB scope, failure logging, indexing)                    (services/processes.py)
│   ├── threadpool.py  thread executor, thread pool lifecycle, active job tracking,
│   │                  ThreadPoolWorkerStatus                                                       (services/executors/threadpool.py, services/processes.py)
│   └── celery/
│       ├── app.py     task names, initialise_celery, get_celery_task                              (services/tasks.py)
│       └── executor.py                                                                            (services/executors/celery.py)
├── workers.py         WorkerStatusMonitor                                                          (services/worker_status_monitor.py)
├── branching/         shared parent/child step storage for all branch kinds                        (beta/parallel/branching.py after graduation)
└── parallel/          concurrent branches: threadpool and Celery dispatch, atomic join             (beta/parallel/ after graduation)
```

The split follows from what `services/processes.py` does today. Its executors import it, and it imports them back
lazily (`get_execution_context`). After the split, `processes/` calls `execution/` and never the other way around,
which removes that cycle.

`process/` and `parallel/` each have their own threadpool and Celery code. That is deliberate. Running a whole process
and running one branch differ: a branch has no input forms, and the last branch to finish has to resume the parent.
Sharing executors would mean adding branch special cases to the process executors.

### Processes package
<!-- diataxis: reference -->

`processes/` is the operations API on processes, used by the interfaces and by downstream code.

| Module | Contents |
|---|---|
| `processes/lifecycle.py` | `create_process`, `start_process`, `restart_process`, `resume_process`, `can_be_resumed`, `RESUMABLE_STATUSES`, `abort_process`, `delete_process`, `set_process_status`, `ensure_correct_process_status`, `_async_resume_processes` |
| `processes/callbacks.py` | `ensure_correct_callback_token`, `continue_awaiting_process`, `update_awaiting_process_progress` (+ async), `replace_current_step_state` (+ async), `fail_awaiting_process` |
| `processes/queries.py` | `_get_process` (made public), `get_process_async`, `process_steps_loader`, `_get_running_processes` |
| `processes/input_state.py` | `retrieve_input_state`, `store_input_state` (from `services/input_state.py`) |
| `processes/schemas.py` | `ProcessSchema`, `ProcessStepSchema`, … (from `schemas/process.py`) |
| `processes/presentation.py` | `enrich_process`, `enrich_step_details`, … (from `utils/enrich_process.py`) |
| `processes/__init__.py` | `SYSTEM_USER`, error messages |

`_get_process` and `get_process_async` currently call `raise_status(HTTPStatus.NOT_FOUND)`. They should raise a
not-found exception from `errors.py` instead, which `api/` maps to a 404 (principle 3).

### Subscriptions and catalog
<!-- diataxis: reference -->

`services/subscriptions.py` (800 lines) mixes four concerns:

| Module | Contents |
|---|---|
| `subscriptions/operations.py` | `get_subscription` (+ async), `create_subscription`, `update_subscription`, the status transitions (`activate_`, `provision_`, `migrate_`, `terminate_subscription`, `unsync`, `resync`, …), `store_process_subscription_relation` |
| `subscriptions/relations.py` | `select_`/`query_in_use_by_subscriptions`, `select_`/`query_depends_on_subscriptions`, `status_relations`, `get_relations`, all of `services/subscription_relations.py` |
| `subscriptions/workflows.py` | `subscription_workflows`, `WF_USABLE_MAP`, `TARGET_DEFAULT_USABLE_MAP`, subscription validations from `services/workflows.py` |
| `subscriptions/presentation.py` | `build_domain_model`, `build_extended_domain_model`, `format_extended_domain_model`, `format_special_types`, `inject_in_use_by_ids_v2`, `_generate_etag`, `utils/get_subscription_dict.py` |
| `subscriptions/schemas.py` | from `schemas/subscription.py`, `schemas/subscription_descriptions.py` |

`domain/customer_description.py` contains CRUD functions, not models, and moves to `subscriptions/customer_descriptions.py`.

`catalog/` covers the read-mostly definitions that workflows and subscriptions refer to: `services/products.py`,
`services/resource_types.py`, `services/fixed_inputs.py` together with `utils/fixed_inputs.py`, the workflow table
lookups from `services/workflows.py`, and `services/workflow_user_guides.py`. Its schemas come from
`schemas/{product,product_block,resource_type,fixed_input,workflow}.py`, and `_to_workflow_schema` moves to
`catalog/presentation.py`.

### Schemas and conversion
<!-- diataxis: mixed -->

`schemas/` holds the Pydantic models of the API contract. GraphQL builds its types from them with `from_pydantic`, so
REST, GraphQL and MCP share them. Of its 15 modules, 11 are only imported by `api`, `graphql` and `mcp`. The others
are `engine_settings` (also used by `services` and `metrics`), `workflow` (`services/workflows.py`), `resource_type`
(`search` indexing) and `schedules`.

Each schema moves into its feature as `<feature>/schemas.py`, with the conversion from ORM rows into
`<feature>/presentation.py`. The interfaces import both from the feature. Conversion logic is needed either way, and
already exists, spread over several packages:

- `utils/enrich_process.py`, used by REST and GraphQL;
- the `build_*`/`format_*` functions in `services/subscriptions.py`;
- `utils/get_subscription_dict.py`;
- `_to_workflow_schema` in `services/workflows.py`.

Giving each feature one `presentation.py` gathers this code in a predictable place. It also fixes a problem with
moving it to `api/`, which this design first proposed: GraphQL would then import from `api`.

Rules for this split:

- A schema that mirrors a table converts with `Schema.model_validate(row, from_attributes=True)`, without a function
  of its own. `presentation.py` contains only conversions that add or reshape data, such as `enrich_process` and
  `build_extended_domain_model`.
- Operations in a feature don't import its `schemas.py` or `presentation.py`. Those exist for the interfaces. Internal
  models that aren't part of the API move to the code that uses them: `WorkerStatus` goes to `execution/workers.py`,
  `EngineSettingsSchema` to `execution/engine_status.py`.
- Schemas refer to each other across features (`ProcessSchema` contains `SubscriptionSchema`, which contains
  `ProductBaseSchema`). These references must stay acyclic: `processes` → `subscriptions` → `catalog`. The
  import-linter checks this.
- `OrchestratorBaseModel` (the datetime-as-epoch wire format) has no core dependencies and moves to
  `utils/pydantic.py`. `ProblemDetail` moves to `api/`.

After this, `schemas/` is empty and is removed.

### Replacing services
<!-- diataxis: explanation -->

"Services" says only that the code isn't an interface or a model. That is why unrelated code ended up there. I
considered several other names for the layer:

| Name | Assessment |
|---|---|
| `operations` | the closest fit for `create_process` or `terminate_subscription`, but would still attract infrastructure code |
| `usecases` / `application` | clean-architecture terms; precise for that audience but unfamiliar to most users, and `application` clashes with `app.py` |
| `managers` / `handlers` | `handlers` suggests event or HTTP handlers; `managers` is already used for distlock and websocket managers |

Every layer name has the same weakness: the question "where does X go" is still answered by "what kind of code is
it" instead of "what feature is it". The proposal therefore removes the layer. Each module goes to the feature it
serves:

| From `services/` | To |
|---|---|
| `processes.py` | `processes/`, `execution/`, `workflow/state.py` |
| `executors/`, `tasks.py`, `worker_status_monitor.py` | `execution/process/`, `execution/workers.py` |
| `parallel.py` | `beta/parallel/worker.py` (now), `execution/parallel/` (on graduation) |
| `input_state.py` | `processes/input_state.py` |
| `subscriptions.py`, `subscription_relations.py`, `process_subscription.py` | `subscriptions/` |
| `products.py`, `resource_types.py`, `fixed_inputs.py`, `workflows.py`, `workflow_user_guides.py` | `catalog/` (validation parts of `workflows.py` → `subscriptions/workflows.py`) |
| `settings.py` | `execution/engine_status.py`. Its current name is easily mistaken for `core/settings.py` |
| `settings_env_variables.py` | `settings/exposed.py` |
| `process_broadcast_thread.py` | `websocket/` |
| `flower.py` | `metrics/` |
| `translations.py` | `forms/translations.py` |

If a layer name turns out to be needed after all, `operations` is the preferred choice.

### Builtins package
<!-- diataxis: reference -->

`workflows/` currently holds two different things: the workflow registry, which is part of the framework, and the
workflows, tasks and steps that ship with the orchestrator. The registry moves to `workflow/registry.py`, and the rest
becomes `builtins/`. That also removes the confusion between `workflow` and `workflows`.

| Module | Contents | From |
|---|---|---|
| `builtins/workflows/` | `modify_note` | `workflows/modify_note.py` |
| `builtins/tasks/` | `task_clean_up_tasks`, `task_resume_workflows`, `task_validate_*` | `workflows/tasks/` |
| `builtins/steps.py` | `resync`, `unsync`, `store_process_subscription`, `set_status`, `refresh_*_search_index` | `workflows/steps.py` |
| `builtins/predicates.py` | `no_uncompleted_instance`, `awaiting_callbacks_exist` | `workflows/predicates.py` |
| `builtins/lifecycle.py` | `create_workflow`, `modify_workflow`, `terminate_workflow`, `validate_workflow`, `reconcile_workflow`, `obsolete_step`, `ensure_provisioning_status` | `workflows/utils.py` |
| `builtins/translations/` | `en-GB.json` | `workflows/translations/` |

The registry entries for the built-ins (`LazyWorkflowInstance(".modify_note", …)`) move to `builtins/__init__.py`.

### Utils package
<!-- diataxis: reference -->

These modules stay, because they already meet principle 2:

- `datetime`, `functional`, `json`, `strings`, `singledispatch`, `crypt`, `get_updated_properties`;
- `helpers`, merged into `strings`, since it only does case conversion;
- `typing`, new, from `types.py`.

The others move:

| Module | To |
|---|---|
| `auth.py` | `security/` |
| `errors.py` | `errors.py` (top-level) |
| `enrich_process.py` | `processes/presentation.py` |
| `get_subscription_dict.py` | `subscriptions/presentation.py` |
| `fixed_inputs.py` | `catalog/` |
| `state.py` | `workflow/state.py` |
| `docs.py` | `cli/generator/` |
| `redis.py`, `redis_client.py` | `websocket/` (`RedisBroadcast`) and a new top-level `redis.py` (client factories). The client depends on settings, so it can't stay in `utils` |
| `search_query.py` | `db/search_query.py`, next to `SearchQuery`; together with `add_subscription_search_query_filter` from `api/helpers.py`. That makes clear it is unrelated to `search/` |
| `deprecation_logger.py`, `validate_data_version.py` | `api/` |
| `expose_settings.py` | `settings/exposed.py` |

### Other packages
<!-- diataxis: reference -->

| Package | Change |
|---|---|
| `api` | `api/models.py` (`delete`, `delete_async`) → `db/helpers.py`; generic dict helpers in `api/helpers.py` (`update_in`, `getattr_in`) → `utils/functional.py` |
| `schedules` | joined by `forms/scheduler_form.py`, `forms/apscheduler_dow_fix.py`, `schemas/schedules.py` (as `schedules/schemas.py`) |
| `mcp` | joined by `schemas/mcp_tools.py`, `schemas/mcp_search.py` |
| `search` | joined by `schemas/search.py`, `schemas/search_requests.py` (into `search/schemas/`) |
| `schemas` | removed; see [Schemas and conversion](#schemas-and-conversion) |
| `metrics` | joined by `services/flower.py` |
| `websocket` | joined by `services/process_broadcast_thread.py` and `RedisBroadcast` |
| `domain` | loses `customer_description.py`; gains the domain types from `types.py` |
| `cli`, `db`, `distlock`, `forms`, `graphql`, `migrations`, `testing`, `devtools` | unchanged, apart from the additions above |

## Loop steps
<!-- diataxis: explanation -->

The loop primitive from [#1947](https://github.com/workfloworchestrator/orchestrator-core/issues/1947) shows how the
`execution/` split holds up for a new kind of branching. The
[analysis in that issue](https://github.com/workfloworchestrator/orchestrator-core/issues/1947#issuecomment-6689819288)
concludes that loop shares the parent/child step *storage* with parallel steps, but not the *execution*: loop runs
iterations one after another in the process, carries state from one iteration to the next, and must allow input steps
and callbacks inside an iteration. That maps onto the layout as follows:

```
beta/loop/                    while in beta
├── dsl.py                    loop(name, steps, *, until, limit, on_error)       → workflow/loop.py
└── engine.py                 sequential iteration, until/limit/on_error         → execution/loop/

execution/branching/          shared: fork step create/update, child step logging with a configurable
                              name prefix ("Branch n", "Iteration n"), latest attempt per branch, BranchKind
execution/recovery.py         + resuming inside a child step (the missing capability)
execution/parallel/           not used by loop
```

Two consequences for the work ahead:

- When loop work starts while parallel steps are still in beta, the shared storage moves from `beta/parallel/branching.py`
  to `beta/branching/`, so that `beta/loop` doesn't depend on parallel internals.
- Resuming inside a child step belongs in `execution/recovery.py`, not in `loop`. Built there, it can also be used to
  allow input steps in parallel branches, which the parallel design lists as a future enhancement.

## Upgrade path
<!-- diataxis: mixed -->

### Compatibility
<!-- diataxis: explanation -->

The restructuring is planned for a future major release. Old import paths stop working in that release; there is no
compatibility layer. Users run a migration script instead, following the 5.0 release, which moved every import
path from `orchestrator` to `orchestrator.core` with `migrate_50.py` and an old → new table in the upgrade guide.

- **One mapping as the source of truth.** A table of old path → new path drives the migration script, the old → new
  table in the upgrade guide, and a test that every entry resolves. Entries are per module for modules that move
  whole, and per symbol for modules that are split (`workflow.py`, `services/processes.py`,
  `services/subscriptions.py`, `types.py`, …).
- **No compatibility layer.** Keeping old paths importable, with shim modules or a `sys.meta_path` import hook, was
  considered and rejected:
  - Its benefit is narrow. Unmigrated code keeps *running* for one more major release. That only helps code that
    can't be migrated together with the upgrade, such as a shared library used by several orchestrators.
  - Type checkers and IDEs don't see it. A downstream project that runs mypy, as most do, has to migrate before its
    CI passes anyway.
  - `mock.patch` on an old path would patch the shim, not the module the code under test uses. The test then fails
    without a clear cause.
  - It isn't small: 150–250 lines plus tests for a hook, because split modules need per-symbol resolution and
    packages need their submodule chain; or about 65 shim files with 1,300 lines.
- **What the script can't fix:** downstream code that relies on private names (underscore functions) or on module-level
  state, such as the thread pool in `services/processes.py`. The upgrade guide lists these cases.
- **Unaffected:**
  - Celery task names, which are strings and don't depend on module paths;
  - workflow names stored in the database;
  - the Alembic location `orchestrator.core.migrations`.
- **Enforcement.** An `import-linter` configuration in `prek` checks:
  - that `utils` imports nothing else from `orchestrator.core`;
  - that stable code doesn't import `beta` outside the listed wiring modules;
  - that feature schemas don't import each other in a cycle;
  - the dependency direction from principle 5.

  Add the first two contracts now; they are already almost true and keep new code in line.

### Migration script
<!-- diataxis: explanation -->

The script reuses the import-rewrite tooling from earlier major releases in `orchestrator/core/devtools/scripts/`:

- `shared.py` provides `move_import` (moves one symbol's import to another module), `remove_imports`, `insert_import`
  and `migrate` (runs a per-file function over a directory and formats the result with ruff);
- `migrate_30.py` used `move_import` per symbol, much like this restructuring needs;
- `migrate_50.py` rewrote module prefixes with regexes.

A new `migrate_60.py` (named after the release) is run the same way as before:
`uv run -m orchestrator.core.devtools.scripts.migrate_60 <dir>`. Unlike `migrate_30.py`, it doesn't list moves by
hand. It reads them from the mapping, so the script and the upgrade guide can't disagree.

Dotted module paths also appear in strings, as the 5.0 upgrade guide shows: Celery's
`include=["orchestrator.core.services.tasks"]`, `strawberry.lazy("orchestrator.core.graphql.schemas…")` and
`mock.patch("…")` targets. The script handles them depending on how the module moved:

- **Module moved whole:** imports and strings are rewritten. A symbol used in a module that moved whole is used in the
  new module in exactly the same way, so this is safe, including for `mock.patch` targets.
- **Module split:** imports are rewritten per symbol. Strings are only *reported*, with file and line, because a patch
  target has to name the module where a symbol is used, and the script can't know which of the new modules that is.
  These reports are the only cases that need a person.

Improvements to `shared.py`, which later migrations also benefit from:

| Today | Improvement |
|---|---|
| Runs `ruff check --fix` on the whole target directory *before* migrating. That applies unrelated fixes from the user's own ruff config, and aborts if the code already has lint errors | Don't touch the code before migrating. Afterwards, only sort imports and format the files that changed (`ruff check --select I --fix`, `ruff format`); `--no-format` skips this |
| Writes files in place without a preview | `--dry-run` prints a unified diff and writes nothing |
| Accepts one directory | Accepts several files and directories; skips `.venv`, `.git` and `node_modules` |
| Prints `f.name` only, which is ambiguous for files with the same name in different packages | Prints paths relative to the target, and a summary per moved module |
| `remove_imports` doesn't handle aliases (`from x import y as z`), and `import orchestrator.core.x` is ignored | Handles `as` aliases. Reports `import module` statements with attribute access, which can't be rewritten safely |
| String references are ignored | Rewrites dotted paths in strings for modules that moved whole, and reports them for split modules (see above) |
| Exit code 1 for any failure | Distinct exit codes for "nothing to do", "migrated" and "migrated, but manual follow-up reported" |

The regex approach in `shared.py` assumes ruff-formatted code, and that remains true for the import statements it
rewrites. LibCST would be more robust, but adds a dependency to a script that runs once per major release. Switch to
it only if the alias and multi-line cases turn out to be too fragile in tests.

### Size estimate
<!-- diataxis: reference -->

A rough estimate for implementing the whole target layout, measured on this branch. The code base has 376 files under
`orchestrator/core` and 454 under `test/`.

| Part | Files | Lines added / removed |
|---|---|---|
| Modules moved whole (60 files, 6,900 lines), shown by git as renames | ~60 renamed | only their changed imports, counted below |
| Modules split (`workflow.py`, `services/processes.py`, `services/subscriptions.py`, `types.py`, `services/workflows.py`, `services/settings.py`, `workflows/__init__.py`, `api/helpers.py`; 5,450 lines) | ~8 removed, ~30 added | +5,500 / −5,450 |
| New package `__init__.py` files | ~15 added | +200 |
| Import rewrites in `orchestrator/` (297 statements, 477 lines, in 119 files) | ~60 changed in place (the others are renames above) | +550 / −480 |
| Import rewrites in `test/` (300 statements, 592 lines, in 157 files), including ~48 test files that follow their module | ~48 renamed, ~110 changed | +650 / −590 |
| `mock.patch` targets and other dotted strings in `test/` | included in the test files above | +205 / −205 |
| Docs: 23 pages, 72 references | 23 changed | +80 / −75 |
| Mapping and its test | ~2 added | +350 |
| Migration script, `shared.py` improvements and their tests | ~3 added, 1 changed | +650 / −50 |
| Upgrade guide | 1 added | +250 |
| **Total** | **~355 files: ~110 renamed, ~50 added, ~10 removed, ~190 changed** | **~+8,900 / −6,850** |

About 7,000 of the added lines are moved code, not new code. `git diff -M --color-moved` shows them as moves. What
actually needs review is about 1,300 lines (the mapping, the script, the tests and the guide), plus the cut points of
the eight split modules.

That is too big for one reviewable PR. Split it along the [order of work](#order-of-work), with one PR per step,
merged into a release branch for the major release. Each PR adds its own entries to the mapping.

## Order of work
<!-- diataxis: reference -->

Now, in PR #1444:

1. Add `orchestrator/core/beta/` with the policy in its docstring, and move the parallel steps code into
   `beta/parallel/`, as described in [Parallel steps](#parallel-steps).
2. Move the parallel tests into `beta/parallel/` test packages, and mark the parallel docs as beta.

Before the major release, in minor releases, without breaking anything:

3. Add the `import-linter` contracts for `utils` and `beta`.
4. Write new code in the target layout where the target package already exists. Don't create half-empty target
   packages ahead of time.

In the major release:

5. Add the mapping and `migrate_60.py`, with the `shared.py` improvements.
6. Move packages in this order, smallest dependency surface first:
   1. `config`, `exception_handlers`, `targets`;
   2. `utils`, `types`;
   3. the feature packages (`schedules`, `mcp`, `settings`, `catalog`, `subscriptions`), each with its schemas and
      presentation;
   4. `builtins`;
   5. `execution` and `processes`;
   6. `workflow`.

   Each step runs `migrate_60.py` on `orchestrator/` and `test/` for its own import rewrites, so the script is tested
   on the code base itself before users run it.
