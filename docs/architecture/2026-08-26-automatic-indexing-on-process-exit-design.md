# Automatic Process & Subscription Indexing on Exit

**Date:** 2026-08-26  
**Status:** Design  
**Epic:** Refactor process/subscription indexing away from workflow steps

## Problem Statement

Currently, search indexing of processes and subscriptions happens via two workflow steps (`refresh_subscription_search_index`, `refresh_process_search_index`) that are manually wired into four workflow decorators. This design has three concrete defects:

1. **Coverage gap:** Indexing only runs on successful step completion. Workflows that fail mid-execution, are aborted, or suspended never get indexed — their data becomes invisible to search.

2. **Stale status:** The indexing steps run *before* the `done` step, so the indexed process record in the search database shows `last_status="running"` and `last_step="Refresh process search index"` forever — never the actual terminal status (completed, failed, aborted, etc.). Only a manual CLI reindex or the `PATCH /processes/{id}` API endpoint's yield-dependency fixes this.

3. **Incomplete coverage:** Workflows using `@task()`, `@workflow()` (raw), or `@validate_workflow` decorators are never indexed at all, since these decorators don't include the indexing steps in their default step lists.

Additionally, the index-on-every-workflow-completion model performs a full `REFRESH MATERIALIZED VIEW subscriptions_search` unconditionally (even if no subscription changed), which does not scale. The legacy Postgres MV already has DEFERRABLE constraint triggers on the underlying tables that refresh it on data changes, making the explicit refresh redundant.

## Solution Overview

Move indexing from being a workflow step to being an automatic lifecycle hook invoked whenever a process "exits" (completes, fails, aborts, suspends, or awaits callback). This hook will:

- Run at three strategic call sites where process execution ends: after threadpool/celery runs (`_run_process_async`), after synchronous abort (`abort_process`), and after callback timeout (`fail_awaiting_process`).
- Extract subscription identifiers from the process's final state dict.
- Index the process and each subscription found.
- Run *after* the process's final status is durably committed to the database, fixing the stale-status bug.
- Run regardless of success/failure/abort/suspend, covering all process types.

## Design

### Architecture

**New module:** `orchestrator/core/search/indexing/hooks.py`

Public function:
```python
def index_process_and_subscriptions(process_id: UUID, result: WFProcess) -> None:
    """Index a process and subscriptions found in its final state.

    Called whenever a process exits (completes, fails, aborts, suspends, awaits callback).
    Designed to be invoked from three call sites in orchestrator/core/services/processes.py.

    Args:
        process_id: UUID of the process to index.
        result: The final Process monad (WFProcess) from the process's run/abort/fail operation.
                Use result.unwrap() to access the final state dict.
    """
```

**Call sites (3 total):**

1. **`orchestrator/core/services/processes.py:_run_process_async.run()`**  
   After `db.session.commit()` in the finally block, inside `with db.database_scope():`. Covers:
   - Successful workflow completion
   - Internally-caught Failed steps (steps that return Failed without raising Python exceptions)
   - Suspended/waiting/awaiting_callback pauses
   - Rare "unknown workflow failure" path (optional, best-effort due to DB access loss)

   Call pattern:
   ```python
   finally:
       db.session.commit()
   _safe_broadcast_process_update(process_id, broadcast_func)
   # NEW: Index process on exit
   try:
       from orchestrator.core.search.indexing.hooks import index_process_and_subscriptions
       index_process_and_subscriptions(process_id, result)
   except ImportError:
       pass  # search extra not installed
   ```

2. **`orchestrator/core/services/processes.py:abort_process()`**  
   After `abort_wf(...)` returns, before returning to caller. Covers synchronous abort requests via the API.

   Call pattern:
   ```python
   def abort_process(process: ProcessTable, user: str, broadcast_func: Callable | None = None) -> WFProcess:
       pstat = load_process(process)
       pstat.update(current_user=user)
       result = abort_wf(pstat, partial(safe_logstep, broadcast_func=broadcast_func))
       # NEW: Index process on abort
       try:
           from orchestrator.core.search.indexing.hooks import index_process_and_subscriptions
           index_process_and_subscriptions(pstat.process_id, result)
       except ImportError:
           pass
       return result
   ```

3. **`orchestrator/core/services/processes.py:fail_awaiting_process()`**  
   After `fail_awaiting_wf(...)` returns, before returning to caller. Covers processes timing out while awaiting a callback.

   Same pattern as `abort_process()`.

**Lazy import guard:** Each call site wraps the hook call in `try/except ImportError: pass` to keep the `search` extra fully optional. If the search extra is not installed, the hook is silently skipped.

### State Extraction & Subscription Lookup

The hook extracts subscription identifiers from the process's final state and triggers indexing for each.

**Implementation logic:**

1. **Extract state dict:**
   ```python
   state = result.unwrap()
   ```
   This works uniformly on all Process variants (Success, Failed, Suspend, Waiting, AwaitingCallback, Abort, Complete, Skipped). For Waiting/AwaitingCallback which may wrap an error structure, non-dict unwrap results are handled gracefully (skip subscription lookup, still index process).

2. **Collect subscription IDs:**
   Scan the state dict for keys: `"subscription"`, `"subscription_id"`, `"subscriptions"`, `"subscription_ids"`.

   For each key found, extract subscription identifiers via structural pattern matching (`match`/`case` per project style guide):
   - **SubscriptionModel instance:** extract `.subscription_id`
   - **UUID or string:** use directly
   - **Iterable (list, tuple, set):** recurse and extract ids from each element
   - **Unexpected type:** skip gracefully (log at debug level)

   Implementation in a helper function `extract_subscription_ids(state: dict | None) -> set[str]` using `itertools` (chain, filter) to avoid nested loops and imperative control flow (per project style guide). Return a deduplicated set of subscription ID strings.

3. **Trigger indexing:**
   ```python
   from orchestrator.core.search.core.types import EntityType
   from orchestrator.core.search.indexing import run_indexing_for_entity

   # Always index the process itself
   run_indexing_for_entity(EntityType.PROCESS, str(process_id))

   # Index each found subscription
   for subscription_id in extract_subscription_ids(state):
       run_indexing_for_entity(EntityType.SUBSCRIPTION, subscription_id)
   ```

**Edge cases handled gracefully:**
- State is not a dict (Waiting/AwaitingCallback unwrap error structure): skip subscription lookup, still index process.
- No subscription keys in state: skip subscription indexing, still index process.
- Empty subscription ID set after dedup: process still indexed.
- Nested subscription models: extracted via recursive helper.

**Note:** No `reset_search_index()` call (legacy Postgres MV refresh). The materialized view already has DEFERRABLE constraint triggers on subscriptions, fixed_inputs, products, and subscription_instance_values tables; the explicit full-view refresh in the steps was redundant and expensive.

### Configuration & Error Handling

**New setting:** Add to `orchestrator/core/settings.py`, in the `LLMSettings` class:

```python
SEARCH_INDEXING_STRICT: bool = False
```

**Semantics:**
- **False (default, production):** Indexing is best-effort. If indexing fails (e.g., transient embedding API timeout, database error, malformed state), the exception is caught, logged at WARNING level with context (process_id, entity_type), and the hook returns normally. The process itself is not affected.
- **True (dev/test):** Indexing failures propagate immediately, allowing tests and development builds to catch indexing bugs (e.g., breaking changes to the Indexer API, misconfigured entity registry) before production.

**Error handling in the hook:**

```python
try:
    # indexing logic: run_indexing_for_entity calls...
except Exception as ex:
    if llm_settings.SEARCH_INDEXING_STRICT:
        raise
    else:
        logger.warning(
            "Failed to index process/subscriptions",
            process_id=str(process_id),
            exc_info=ex,
        )
```

**ImportError handling (search extra absent):**
Handled at each call site via the `try/except ImportError: pass` guard. If the search extra is not installed, ImportError is caught and indexing is silently skipped. This is independent of `SEARCH_INDEXING_STRICT` (a missing optional extra is not an error, it's unsupported).

### Removal of Old Steps

**Delete from `orchestrator/core/workflows/steps.py`:**
- `refresh_subscription_search_index` function (lines 144–165)
- `refresh_process_search_index` function (lines 168–189)

**Remove wiring from `orchestrator/core/workflows/utils.py`:**
- `create_workflow` decorator: remove `>> refresh_subscription_search_index >> refresh_process_search_index >>` from the steplist (around lines 305–314)
- `modify_workflow` decorator: remove from steplist (around lines 361–371)
- `terminate_workflow` decorator: remove from steplist (around lines 418–429)
- `reconcile_workflow` decorator: remove from steplist (around lines 516–526)

**Remove hand-wired reference from `orchestrator/core/workflows/modify_note.py`:**
- Line 69: remove the refresh step call

**Test updates:**
- `test/unit_tests/workflows/test_utils.py`: Update `step_names` assertions (lines 57–58, 86–87, 112–113, etc.) in `create_workflow`, `modify_workflow`, `terminate_workflow`, and `reconcile_workflow` tests to remove the two refresh-step names from expected step lists.
- `test/unit_tests/workflows/test_steps.py`: Delete `test_refresh_search_index_exception_swallowed` (lines 163–176); the steps no longer exist.

### Testing Strategy

**Unit tests** in new file `test/unit_tests/search/indexing/test_hooks.py`:

All tests use `@pytest.mark.parametrize` to avoid test duplication (per project style guide).

1. **Process indexing is always called:**
   - Parametrized over all Process variants (Success, Complete, Failed, Suspend, Waiting, AwaitingCallback, Abort, Skipped).
   - Verify `run_indexing_for_entity(EntityType.PROCESS, str(process_id))` is called exactly once, regardless of variant.

2. **Subscription lookup — single key forms:**
   - State contains `"subscription": SubscriptionModel(...)` → subscription is indexed
   - State contains `"subscription_id": "uuid-str"` → subscription is indexed
   - State contains `"subscription_id": UUID(...)` → subscription is indexed

3. **Subscription lookup — multiple key forms:**
   - Parametrized: state has `"subscriptions": [...]` (list), `"subscription_ids": [...]` (list), or both `"subscription"` + `"subscription_id"` simultaneously.
   - Verify all are collected and deduped (no duplicate indexing calls).

4. **Subscription lookup — nested models:**
   - State has nested SubscriptionModel (e.g., inside a dict) or a SubscriptionModel with a subscription_id field.
   - Verify extraction still works via the recursive helper.

5. **No subscriptions in state:**
   - State dict is empty or lacks all subscription keys.
   - Verify process is still indexed; no subscription indexing attempted (no extra calls).

6. **Non-dict unwrap (edge case):**
   - Mock `result.unwrap()` to return a non-dict (e.g., an error dict for Waiting/AwaitingCallback).
   - Verify process is still indexed; subscription lookup is skipped gracefully (no exception).

7. **Error handling — strictness=False:**
   - Mock `run_indexing_for_entity` to raise an exception.
   - `SEARCH_INDEXING_STRICT=False`.
   - Verify exception is caught, logged at WARNING, and the hook returns normally.

8. **Error handling — strictness=True:**
   - Same setup as above.
   - `SEARCH_INDEXING_STRICT=True`.
   - Verify exception propagates (raises from the hook).

9. **Search extra not installed:**
   - Mock the import of the hook module to raise ImportError.
   - Verify the call site's `try/except ImportError: pass` guard works; no exception escapes to the caller.

**Integration tests** in `test/integration_tests/workflows/`:

1. **Real workflow end-to-end indexing:**
   - Create and run a real workflow (via test helper or `create_process` + `resume_process` calls).
   - Verify indexing is triggered exactly once after the workflow completes (not during, not multiple times).
   - Verify the indexed process record shows the correct final `last_status` (regression test for the stale-status bug).

2. **Abort process triggers indexing:**
   - Create a process, abort it via `abort_process()`.
   - Verify indexing is triggered with the aborted process.

3. **Fail awaiting process triggers indexing:**
   - Create a process in AWAITING_CALLBACK state, trigger `fail_awaiting_process()`.
   - Verify indexing is triggered.

4. **Subscription extraction from various state forms:**
   - Run workflows with different subscription storage patterns (single SubscriptionModel, subscription_id UUID, nested forms).
   - Verify the correct subscription(s) are indexed in each case.

### Backward Compatibility

**Breaking change:** The two workflow steps are deleted entirely. Downstream repositories that reference these step names in custom step lists will fail to import.

**Mitigation:** Include in the release CHANGELOG:
```
BREAKING: The `refresh_subscription_search_index` and `refresh_process_search_index` workflow steps have been removed. Indexing now happens automatically when processes exit. If you have custom workflows that reference these steps by name (e.g., `>> refresh_subscription_search_index >>`), remove those references.
```

## Benefits

1. **Fixes coverage gap:** All process exits (complete, failed, aborted, suspended, awaiting) are now indexed.
2. **Fixes stale-status bug:** Indexing reads from the database after the final status is committed, so the indexed record has correct `last_status`.
3. **Covers all workflow types:** Including `@task()`, `@workflow()`, `@validate_workflow`, and custom step lists.
4. **Better error isolation:** Indexing failures don't affect the process itself (best-effort by default).
5. **Removes redundant MV refresh:** Legacy Postgres FTS indexing relies on already-present DB triggers.
6. **Simpler mental model:** Indexing is automatic and implicit, not a manual step that can be forgotten.

## Implementation Plan

This spec is ready for the `writing-plans` skill, which will produce a detailed step-by-step implementation plan with task decomposition and verification checkpoints.
