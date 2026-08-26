# Automatic Process & Subscription Indexing on Exit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Index a process and its subscriptions automatically whenever a process exits (completes, fails, aborts, suspends, awaits callback), instead of relying on two workflow steps that only run on the happy path.

**Architecture:** A new hook module `orchestrator/core/search/indexing/hooks.py` exposes `index_process_and_subscriptions(process_id, result)`. It is invoked from three process-exit call sites in `orchestrator/core/services/processes.py` via a small `_safe_index_process` wrapper that keeps the `search` extra optional. Subscription ids are read out of the process's final state dict. The two existing indexing workflow steps are deleted.

**Tech Stack:** Python 3.11+, pytest, structlog, pydantic-settings, SQLAlchemy. Package manager `uv`.

**Spec:** `docs/architecture/2026-08-26-automatic-indexing-on-process-exit-design.md`

## Global Constraints

- Line length **120**; formatter/linter is `ruff`; type checker is `mypy` (annotations required everywhere).
- **No relative imports** — all imports absolute (`ban-relative-imports = "all"`).
- Every new file MUST start with the Apache-2.0 copyright header used throughout the repo (pre-commit hook `copyright headers are present` enforces this):
  ```python
  # Copyright 2019-2026 SURF, GÉANT.
  # Licensed under the Apache License, Version 2.0 (the "License");
  # you may not use this file except in compliance with the License.
  # You may obtain a copy of the License at
  #
  #    http://www.apache.org/licenses/LICENSE-2.0
  #
  # Unless required by applicable law or agreed to in writing, software
  # distributed under the License is distributed on an "AS IS" BASIS,
  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  # See the License for the specific language governing permissions and
  # limitations under the License.
  ```
- Tests: no duplicated test bodies that differ only in data — use `@pytest.mark.parametrize` with `pytest.param(..., id="label")`.
- Prefer `itertools` / comprehensions over imperative loops; prefer `match`/`case` over `isinstance` chains; no `break`/`continue`.
- All tests touching the `search` subsystem set `pytestmark = pytest.mark.search` (module level), matching `test/unit_tests/search/indexing/test_tasks.py:29`.
- Commands: `uv run pytest <path>`, `uv run mypy orchestrator`, `uv run ruff check orchestrator`, `pre-commit run --all-files`.
- Commit messages: descriptive, **no `Co-Authored-By` line**.

## File Structure

| File | Responsibility |
|---|---|
| `orchestrator/core/search/indexing/hooks.py` (create) | Public hook `index_process_and_subscriptions` + pure helper `extract_subscription_ids`. Only file that knows how state maps to indexable entities. |
| `orchestrator/core/settings.py` (modify) | Add `SEARCH_INDEXING_STRICT` to `LLMSettings`. |
| `orchestrator/core/services/processes.py` (modify) | Add `_safe_index_process` wrapper + 3 call sites at process exit. |
| `orchestrator/core/workflows/steps.py` (modify) | Delete the two indexing steps. |
| `orchestrator/core/workflows/utils.py` (modify) | Remove indexing steps from 4 decorator step lists. |
| `orchestrator/core/workflows/modify_note.py` (modify) | Remove the hand-wired indexing step. |
| `test/unit_tests/search/indexing/test_hooks.py` (create) | Unit tests for extraction + hook behaviour + strictness. |
| `test/unit_tests/services/test_processes_indexing.py` (create) | Unit tests for the `_safe_index_process` wrapper (incl. missing search extra). |
| `test/integration_tests/services/test_indexing_on_exit.py` (create) | End-to-end: real process runs/aborts trigger indexing with correct final status. |
| `test/unit_tests/workflows/test_utils.py` (modify) | Drop deleted step names from expected step lists. |
| `test/unit_tests/workflows/test_steps.py` (modify) | Delete obsolete step test + imports. |

---

### Task 1: Subscription-id extraction helper + strictness setting

**Files:**
- Create: `orchestrator/core/search/indexing/hooks.py`
- Modify: `orchestrator/core/settings.py:147-173` (`LLMSettings`)
- Test: `test/unit_tests/search/indexing/test_hooks.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `extract_subscription_ids(state: object) -> set[str]` in `orchestrator.core.search.indexing.hooks`
  - `SUBSCRIPTION_STATE_KEYS: tuple[str, ...]` in the same module
  - `llm_settings.SEARCH_INDEXING_STRICT: bool` (default `False`)

- [ ] **Step 1: Write the failing tests**

Create `test/unit_tests/search/indexing/test_hooks.py` (with the copyright header from Global Constraints, then):

```python
"""Tests for the process-exit indexing hook: state extraction, entity indexing and strictness."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from orchestrator.core.search.indexing.hooks import extract_subscription_ids

pytestmark = pytest.mark.search

SUB_ID_A = str(uuid4())
SUB_ID_B = str(uuid4())


@pytest.mark.parametrize(
    "state,expected",
    [
        pytest.param({}, set(), id="empty-state"),
        pytest.param({"unrelated": "value"}, set(), id="no-subscription-keys"),
        pytest.param({"subscription_id": SUB_ID_A}, {SUB_ID_A}, id="subscription-id-str"),
        pytest.param({"subscription_id": None}, set(), id="subscription-id-none"),
        pytest.param({"subscription": {"subscription_id": SUB_ID_A}}, {SUB_ID_A}, id="subscription-serialized-dict"),
        pytest.param(
            {"subscription": SimpleNamespace(subscription_id=SUB_ID_A)}, {SUB_ID_A}, id="subscription-model-like"
        ),
        pytest.param({"subscriptions": [SUB_ID_A, SUB_ID_B]}, {SUB_ID_A, SUB_ID_B}, id="subscriptions-list-of-str"),
        pytest.param(
            {"subscriptions": [{"subscription_id": SUB_ID_A}, SimpleNamespace(subscription_id=SUB_ID_B)]},
            {SUB_ID_A, SUB_ID_B},
            id="subscriptions-list-mixed",
        ),
        pytest.param({"subscription_ids": (SUB_ID_A, SUB_ID_B)}, {SUB_ID_A, SUB_ID_B}, id="subscription-ids-tuple"),
        pytest.param(
            {"subscription": SimpleNamespace(subscription_id=SUB_ID_A), "subscription_id": SUB_ID_A},
            {SUB_ID_A},
            id="duplicates-deduped",
        ),
        pytest.param({"subscription": "not-a-uuid-but-a-string"}, {"not-a-uuid-but-a-string"}, id="opaque-string"),
        pytest.param({"subscription": 42}, set(), id="unsupported-type-ignored"),
        pytest.param("not-a-dict", set(), id="state-not-a-dict"),
        pytest.param(None, set(), id="state-none"),
    ],
)
def test_extract_subscription_ids(state, expected):
    assert extract_subscription_ids(state) == expected


def test_extract_subscription_ids_accepts_uuid_objects():
    subscription_id = uuid4()
    assert extract_subscription_ids({"subscription_id": subscription_id}) == {str(subscription_id)}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest test/unit_tests/search/indexing/test_hooks.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'orchestrator.core.search.indexing.hooks'`

- [ ] **Step 3: Add the strictness setting**

In `orchestrator/core/settings.py`, inside `LLMSettings`, directly after the `LLM_FORCE_EXTENSION_MIGRATION: bool = False` line (currently line 173):

```python
    # Indexing behaviour
    SEARCH_INDEXING_STRICT: bool = False  # Raise on indexing errors (dev/test); log and continue by default
```

- [ ] **Step 4: Create the hook module with the extraction helper**

Create `orchestrator/core/search/indexing/hooks.py` (copyright header first, then):

```python
"""Indexing hook invoked when a process exits.

Replaces the former `refresh_subscription_search_index` / `refresh_process_search_index`
workflow steps, so that indexing also happens for failed, aborted and suspended processes.
"""

from collections.abc import Iterable
from itertools import chain
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

if TYPE_CHECKING:
    from orchestrator.core.workflow import Process as WFProcess

logger = structlog.get_logger(__name__)

SUBSCRIPTION_STATE_KEYS = ("subscription", "subscription_id", "subscriptions", "subscription_ids")


def _extract_ids(value: object) -> Iterable[str]:
    """Return subscription ids found in a single state value."""
    match value:
        case UUID():
            return (str(value),)
        case str():
            return (value,)
        case {"subscription_id": subscription_id}:
            return _extract_ids(subscription_id)
        case list() | tuple() | set():
            return chain.from_iterable(map(_extract_ids, value))
        case _ if (subscription_id := getattr(value, "subscription_id", None)) is not None:
            return _extract_ids(subscription_id)
        case _:
            return ()


def extract_subscription_ids(state: object) -> set[str]:
    """Collect unique subscription ids from a workflow's final state.

    Args:
        state: The unwrapped process state. Anything that is not a dict yields an empty set,
            because suspended/waiting processes may carry an error structure instead of a state.

    Returns:
        Deduplicated subscription ids as strings.
    """
    if not isinstance(state, dict):
        return set()

    values = (state.get(key) for key in SUBSCRIPTION_STATE_KEYS)
    return set(chain.from_iterable(map(_extract_ids, values)))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest test/unit_tests/search/indexing/test_hooks.py -v`
Expected: PASS (15 tests)

- [ ] **Step 6: Type-check and lint**

Run: `uv run mypy orchestrator/core/search/indexing/hooks.py && uv run ruff check orchestrator/core/search/indexing/hooks.py orchestrator/core/settings.py`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add orchestrator/core/search/indexing/hooks.py orchestrator/core/settings.py test/unit_tests/search/indexing/test_hooks.py
git commit -m "Add subscription-id extraction helper and SEARCH_INDEXING_STRICT setting for process-exit indexing"
```

---

### Task 2: The `index_process_and_subscriptions` hook

**Files:**
- Modify: `orchestrator/core/search/indexing/hooks.py`
- Test: `test/unit_tests/search/indexing/test_hooks.py`

**Interfaces:**
- Consumes: `extract_subscription_ids`, `llm_settings.SEARCH_INDEXING_STRICT` (Task 1); `run_indexing_for_entity(entity_kind: EntityType, entity_id: str | None = None, ...)` from `orchestrator.core.search.indexing.tasks`; `EntityType.PROCESS` / `EntityType.SUBSCRIPTION` from `orchestrator.core.search.core.types`.
- Produces: `index_process_and_subscriptions(process_id: UUID, result: "WFProcess") -> None` in `orchestrator.core.search.indexing.hooks`. `result` only needs to provide `.unwrap()`.

- [ ] **Step 1: Write the failing tests**

Append to `test/unit_tests/search/indexing/test_hooks.py`:

```python
from unittest.mock import call, patch

from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.indexing.hooks import index_process_and_subscriptions
from orchestrator.core.settings import llm_settings
from orchestrator.core.workflow import (
    Abort,
    AwaitingCallback,
    Complete,
    Failed,
    Skipped,
    Success,
    Suspend,
    Waiting,
)


@pytest.mark.parametrize(
    "process_variant",
    [
        pytest.param(Success, id="success"),
        pytest.param(Skipped, id="skipped"),
        pytest.param(Complete, id="complete"),
        pytest.param(Suspend, id="suspend"),
        pytest.param(Abort, id="abort"),
        pytest.param(Waiting, id="waiting"),
        pytest.param(AwaitingCallback, id="awaiting-callback"),
        pytest.param(Failed, id="failed"),
    ],
)
@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_process_is_always_indexed(mock_run_indexing, process_variant):
    process_id = uuid4()

    index_process_and_subscriptions(process_id, process_variant({}))

    mock_run_indexing.assert_called_once_with(EntityType.PROCESS, str(process_id))


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_subscriptions_from_state_are_indexed(mock_run_indexing):
    process_id = uuid4()

    index_process_and_subscriptions(process_id, Success({"subscription_id": SUB_ID_A}))

    assert mock_run_indexing.call_args_list == [
        call(EntityType.PROCESS, str(process_id)),
        call(EntityType.SUBSCRIPTION, SUB_ID_A),
    ]


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_non_dict_state_still_indexes_process(mock_run_indexing):
    process_id = uuid4()

    index_process_and_subscriptions(process_id, Failed(RuntimeError("boom")))

    mock_run_indexing.assert_called_once_with(EntityType.PROCESS, str(process_id))


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_indexing_error_is_swallowed_when_not_strict(mock_run_indexing, monkeypatch):
    monkeypatch.setattr(llm_settings, "SEARCH_INDEXING_STRICT", False)
    mock_run_indexing.side_effect = RuntimeError("index error")

    index_process_and_subscriptions(uuid4(), Success({}))  # must not raise


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_indexing_error_is_raised_when_strict(mock_run_indexing, monkeypatch):
    monkeypatch.setattr(llm_settings, "SEARCH_INDEXING_STRICT", True)
    mock_run_indexing.side_effect = RuntimeError("index error")

    with pytest.raises(RuntimeError, match="index error"):
        index_process_and_subscriptions(uuid4(), Success({}))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest test/unit_tests/search/indexing/test_hooks.py -v`
Expected: FAIL with `ImportError: cannot import name 'index_process_and_subscriptions'`

- [ ] **Step 3: Implement the hook**

In `orchestrator/core/search/indexing/hooks.py`, add these imports below the existing ones:

```python
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.indexing.tasks import run_indexing_for_entity
from orchestrator.core.settings import llm_settings
```

and append the public hook:

```python
def index_process_and_subscriptions(process_id: UUID, result: "WFProcess") -> None:
    """Index a process and every subscription referenced by its final state.

    Called whenever a process exits: completed, failed, aborted, suspended or awaiting callback.
    Runs after the process' final status has been committed, so the indexed record carries the
    real terminal status.

    Args:
        process_id: The process to index.
        result: Final process value; `unwrap()` provides the state to scan for subscriptions.

    Raises:
        Exception: Only when `llm_settings.SEARCH_INDEXING_STRICT` is True. Otherwise failures
            are logged and swallowed so indexing can never break a process.
    """
    try:
        run_indexing_for_entity(EntityType.PROCESS, str(process_id))
        for subscription_id in extract_subscription_ids(result.unwrap()):
            run_indexing_for_entity(EntityType.SUBSCRIPTION, subscription_id)
    except Exception as ex:
        if llm_settings.SEARCH_INDEXING_STRICT:
            raise
        logger.warning("Failed to index process and subscriptions", process_id=str(process_id), error=str(ex))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest test/unit_tests/search/indexing/test_hooks.py -v`
Expected: PASS (all tests, including the 8 parametrized process variants)

- [ ] **Step 5: Type-check and lint**

Run: `uv run mypy orchestrator/core/search/indexing/hooks.py && uv run ruff check orchestrator/core/search/indexing/hooks.py`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add orchestrator/core/search/indexing/hooks.py test/unit_tests/search/indexing/test_hooks.py
git commit -m "Add index_process_and_subscriptions hook with configurable strictness"
```

---

### Task 3: Invoke the hook at the three process-exit call sites

**Files:**
- Modify: `orchestrator/core/services/processes.py` (add wrapper near `_safe_broadcast_process_update` at line 88; call sites at `_run_process_async` line ~443, `abort_process` line ~794, `fail_awaiting_process` line ~801)
- Test: `test/unit_tests/services/test_processes_indexing.py`

**Interfaces:**
- Consumes: `index_process_and_subscriptions` (Task 2).
- Produces: `_safe_index_process(process_id: UUID, result: WFProcess) -> None` in `orchestrator.core.services.processes` — imports the hook lazily and returns silently when the `search` extra is not installed.

- [ ] **Step 1: Write the failing tests**

Create `test/unit_tests/services/test_processes_indexing.py` (copyright header first, then):

```python
"""Tests for process-exit indexing wiring in the processes service."""

import sys
from unittest.mock import patch
from uuid import uuid4

from orchestrator.core.services.processes import _safe_index_process
from orchestrator.core.workflow import Success


@patch("orchestrator.core.search.indexing.hooks.index_process_and_subscriptions")
def test_safe_index_process_calls_hook(mock_hook):
    process_id = uuid4()
    result = Success({})

    _safe_index_process(process_id, result)

    mock_hook.assert_called_once_with(process_id, result)


def test_safe_index_process_is_noop_without_search_extra(monkeypatch):
    # A None entry in sys.modules makes the import raise ImportError, simulating a missing extra.
    monkeypatch.setitem(sys.modules, "orchestrator.core.search.indexing.hooks", None)

    _safe_index_process(uuid4(), Success({}))  # must not raise


@patch("orchestrator.core.search.indexing.hooks.index_process_and_subscriptions")
def test_abort_process_indexes_on_exit(mock_hook):
    process_id = uuid4()
    result = Success({})

    with (
        patch("orchestrator.core.services.processes.load_process") as mock_load,
        patch("orchestrator.core.services.processes.abort_wf", return_value=result),
    ):
        mock_load.return_value.process_id = process_id

        from orchestrator.core.services.processes import abort_process

        assert abort_process(process=None, user="tester") is result

    mock_hook.assert_called_once_with(process_id, result)


@patch("orchestrator.core.search.indexing.hooks.index_process_and_subscriptions")
def test_fail_awaiting_process_indexes_on_exit(mock_hook):
    process_id = uuid4()
    result = Success({})

    with (
        patch("orchestrator.core.services.processes.load_process") as mock_load,
        patch("orchestrator.core.services.processes.fail_awaiting_wf", return_value=result),
    ):
        mock_load.return_value.process_id = process_id

        from orchestrator.core.services.processes import fail_awaiting_process

        assert fail_awaiting_process(process=None) is result

    mock_hook.assert_called_once_with(process_id, result)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest test/unit_tests/services/test_processes_indexing.py -v`
Expected: FAIL with `ImportError: cannot import name '_safe_index_process'`

- [ ] **Step 3: Add the wrapper**

In `orchestrator/core/services/processes.py`, directly below `_safe_broadcast_process_update` (which ends at line 95):

```python
def _safe_index_process(process_id: UUID, result: WFProcess) -> None:
    """Index a process and its subscriptions on exit; no-op when the search extra is not installed."""
    try:
        from orchestrator.core.search.indexing.hooks import index_process_and_subscriptions
    except ImportError:
        return

    index_process_and_subscriptions(process_id, result)
```

- [ ] **Step 4: Wire call site 1 — `_run_process_async`**

In `_run_process_async.run()` (line ~458), add the call directly after the broadcast:

```python
                    finally:
                        db.session.commit()
                    _safe_broadcast_process_update(process_id, broadcast_func)
                    _safe_index_process(process_id, result)
```

Do **not** change the existing `raise` in the `except Exception as ex:` branch — the rare "lost access to database" path stays as-is, since indexing needs a live session.

- [ ] **Step 5: Wire call sites 2 and 3 — abort and fail-awaiting**

Replace `abort_process` and `fail_awaiting_process` (lines 794-804) with:

```python
def abort_process(process: ProcessTable, user: str, broadcast_func: Callable | None = None) -> WFProcess:
    pstat = load_process(process)

    pstat.update(current_user=user)
    result = abort_wf(pstat, partial(safe_logstep, broadcast_func=broadcast_func))
    _safe_index_process(pstat.process_id, result)
    return result


def fail_awaiting_process(process: ProcessTable, broadcast_func: Callable | None = None) -> WFProcess:
    """Fail a process that has been stuck awaiting a callback past its timeout."""
    pstat = load_process(process)
    result = fail_awaiting_wf(pstat, partial(safe_logstep, broadcast_func=broadcast_func))
    _safe_index_process(pstat.process_id, result)
    return result
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest test/unit_tests/services/test_processes_indexing.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Run the surrounding unit suites for regressions**

Run: `uv run pytest test/unit_tests/services test/unit_tests/search -q`
Expected: PASS

- [ ] **Step 8: Type-check and lint**

Run: `uv run mypy orchestrator/core/services/processes.py && uv run ruff check orchestrator/core/services/processes.py`
Expected: no errors

- [ ] **Step 9: Commit**

```bash
git add orchestrator/core/services/processes.py test/unit_tests/services/test_processes_indexing.py
git commit -m "Index processes and subscriptions at every process-exit call site"
```

---

### Task 4: Remove the indexing workflow steps and their wiring

**Files:**
- Modify: `orchestrator/core/workflows/steps.py:144-189` (delete both steps)
- Modify: `orchestrator/core/workflows/utils.py:305-314, 361-371, 417-429, 515-526` (remove from 4 step lists) and its import block
- Modify: `orchestrator/core/workflows/modify_note.py:25, 69`
- Modify: `test/unit_tests/workflows/test_utils.py:51-60, 79-89, 107-115`
- Modify: `test/unit_tests/workflows/test_steps.py:14, 24-30, 163-177`

**Interfaces:**
- Consumes: the working hook from Task 3 (indexing must already happen automatically before the steps are removed).
- Produces: `refresh_subscription_search_index` and `refresh_process_search_index` no longer exist anywhere in the codebase.

- [ ] **Step 1: Update the expected step lists in the existing tests (these now fail)**

In `test/unit_tests/workflows/test_utils.py`, remove these two entries from the `expected_steps` list in **all three** reconcile tests (`test_reconcile_workflow_basic` lines 57-58, `test_reconcile_workflow_additional_steps` lines 86-87, `test_reconcile_workflow_empty_function_steps` lines 112-113):

```python
        "Refresh subscription search index",
        "Refresh process search index",
```

For example `test_reconcile_workflow_basic` becomes:

```python
    expected_steps = [
        "Start",
        "Create Process Subscription relation",
        "Lock subscription",
        "Done",
        "Unlock subscription",
        "Done",
    ]
    assert step_names == expected_steps
```

- [ ] **Step 2: Run those tests to verify they fail**

Run: `uv run pytest test/unit_tests/workflows/test_utils.py -v`
Expected: 3 FAILures — the workflows still contain the refresh steps, so `step_names != expected_steps`

- [ ] **Step 3: Delete the two steps**

In `orchestrator/core/workflows/steps.py`, delete `refresh_subscription_search_index` (lines 144-165) and `refresh_process_search_index` (lines 168-189) in full, and delete the now-unused import on line 21:

```python
from orchestrator.core.services.settings import reset_search_index
```

- [ ] **Step 4: Remove the steps from every step list**

In `orchestrator/core/workflows/utils.py`, delete these two lines from the step lists of `create_workflow` (311-312), `modify_workflow` (368-369), `terminate_workflow` (426-427) and `reconcile_workflow` (523-524):

```python
            >> refresh_subscription_search_index
            >> refresh_process_search_index
```

`create_workflow`'s step list then reads:

```python
        steplist = (
            init
            >> f()
            >> (additional_steps or StepList())
            >> set_status(status)
            >> resync
            >> done
        )
```

In `orchestrator/core/workflows/modify_note.py`, change line 69 to:

```python
    return init >> store_process_subscription() >> store_subscription_note >> done
```

- [ ] **Step 5: Remove every remaining reference (imports)**

Run: `grep -rn "refresh_subscription_search_index\|refresh_process_search_index" orchestrator/ test/`

Delete each remaining hit — the import in `orchestrator/core/workflows/utils.py`, the import in `orchestrator/core/workflows/modify_note.py:25` (keep `store_process_subscription` in that import), and in `test/unit_tests/workflows/test_steps.py` the two names in the import block (lines 24-30), the obsolete test `test_refresh_search_index_exception_swallowed` (lines 163-177) together with its `# --- refresh_search_index ---` comment banner, and the trailing `"and refresh_search_index error handling"` phrase in the module docstring on line 14.

Expected after deletion: `grep` returns no hits.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest test/unit_tests/workflows -q`
Expected: PASS (the 3 updated reconcile tests now match; no import errors in `test_steps.py`)

- [ ] **Step 7: Run the wider unit suite for regressions**

Run: `uv run pytest test/unit_tests -q`
Expected: PASS

- [ ] **Step 8: Type-check and lint**

Run: `uv run mypy orchestrator && uv run ruff check orchestrator`
Expected: no errors (in particular no unused-import warnings in the touched files)

- [ ] **Step 9: Commit**

```bash
git add orchestrator/core/workflows/steps.py orchestrator/core/workflows/utils.py orchestrator/core/workflows/modify_note.py test/unit_tests/workflows/test_utils.py test/unit_tests/workflows/test_steps.py
git commit -m "Remove refresh search index workflow steps now that indexing runs on process exit"
```

---

### Task 5: Integration tests for real process exits

**Files:**
- Create: `test/integration_tests/services/test_indexing_on_exit.py`

**Interfaces:**
- Consumes: `_safe_index_process` wiring (Task 3); `start_process`, `abort_process`, `load_process` from `orchestrator.core.services.processes`; `WorkflowInstanceForTests` from `test.integration_tests.workflows`.
- Produces: no production code — regression coverage only.

**Critical context for the implementer:** the helper `run_workflow()` in `test/integration_tests/workflows/__init__.py:219` calls `runwf()` directly and therefore **bypasses `_run_process_async` and the hook**. These tests must use `start_process(...)` (which routes through the executor; with `app_settings.TESTING` true the threadpool call blocks until the process finishes) or call `abort_process(...)` directly.

- [ ] **Step 1: Write the failing tests**

Create `test/integration_tests/services/test_indexing_on_exit.py` (copyright header first, then):

```python
"""Integration tests asserting that processes and subscriptions are indexed when a process exits."""

from unittest.mock import call, patch

from sqlalchemy import select

from orchestrator.core.db import ProcessTable, db
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.services.processes import abort_process, start_process
from orchestrator.core.targets import Target
from orchestrator.core.workflow import ProcessStatus, done, init, step, workflow
from test.integration_tests.workflows import WorkflowInstanceForTests


@step("Succeeding step")
def succeeding_step():
    return {"result": "ok"}


@step("Failing step")
def failing_step():
    raise ValueError("step blew up")


# No description argument: passing one triggers the deprecation warning in workflow.py:600.
@workflow(target=Target.SYSTEM)
def indexing_success_wf():
    return init >> succeeding_step >> done


@workflow(target=Target.SYSTEM)
def indexing_failure_wf():
    return init >> failing_step >> done


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_completed_process_is_indexed_with_final_status(mock_run_indexing):
    with WorkflowInstanceForTests(indexing_success_wf, "indexing_success_wf"):
        process_id = start_process("indexing_success_wf", [{}])

    process = db.session.get(ProcessTable, process_id)
    assert process.last_status == ProcessStatus.COMPLETED

    # Indexing happened once, after the terminal status was committed.
    assert call(EntityType.PROCESS, str(process_id)) in mock_run_indexing.call_args_list


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_failed_process_is_indexed(mock_run_indexing):
    with WorkflowInstanceForTests(indexing_failure_wf, "indexing_failure_wf"):
        process_id = start_process("indexing_failure_wf", [{}])

    process = db.session.get(ProcessTable, process_id)
    assert process.last_status == ProcessStatus.FAILED

    assert call(EntityType.PROCESS, str(process_id)) in mock_run_indexing.call_args_list


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_aborted_process_is_indexed(mock_run_indexing):
    with WorkflowInstanceForTests(indexing_success_wf, "indexing_abort_wf"):
        process_id = start_process("indexing_abort_wf", [{}])
        process = db.session.get(ProcessTable, process_id)
        mock_run_indexing.reset_mock()

        abort_process(process, user="tester")

    assert call(EntityType.PROCESS, str(process_id)) in mock_run_indexing.call_args_list
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest test/integration_tests/services/test_indexing_on_exit.py -v`
Expected: PASS (3 tests). Reference patterns if registration needs adjusting: `test/integration_tests/services/test_processes.py` and `test/integration_tests/services/test_start_predicate.py:65` both register workflows via `WorkflowInstanceForTests`. The assertions themselves must not be weakened.

- [ ] **Step 3: Verify the subscription path**

Add one further test to the same file, exercising a workflow that puts a subscription id in state:

```python
@step("Store subscription id")
def store_subscription_id_step(subscription_id):
    return {"subscription_id": subscription_id}


@workflow(target=Target.SYSTEM)
def indexing_subscription_wf():
    return init >> store_subscription_id_step >> done


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_subscription_in_state_is_indexed(mock_run_indexing, generic_subscription_1):
    with WorkflowInstanceForTests(indexing_subscription_wf, "indexing_subscription_wf"):
        process_id = start_process("indexing_subscription_wf", [{"subscription_id": generic_subscription_1}])

    assert call(EntityType.SUBSCRIPTION, str(generic_subscription_1)) in mock_run_indexing.call_args_list
    assert call(EntityType.PROCESS, str(process_id)) in mock_run_indexing.call_args_list
```

`generic_subscription_1` is defined at `test/integration_tests/_fixtures.py:810` and yields a subscription id string.

- [ ] **Step 4: Run the full integration file**

Run: `uv run pytest test/integration_tests/services/test_indexing_on_exit.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full suites and pre-commit**

Run: `uv run pytest test/unit_tests -q && uv run pytest test/integration_tests/services -q && pre-commit run --all-files`
Expected: PASS / no findings

- [ ] **Step 6: Commit**

```bash
git add test/integration_tests/services/test_indexing_on_exit.py
git commit -m "Add integration tests for indexing on process completion, failure and abort"
```

---

### Task 6: Document the breaking change

**Files:**
- Modify: the repo's changelog / release notes file (locate with `ls CHANGELOG* docs/CHANGELOG* 2>/dev/null` — if none exists, add the note to `docs/architecture/2026-08-26-automatic-indexing-on-process-exit-design.md` under a new "Release notes" heading instead of creating a changelog file).

**Interfaces:**
- Consumes: the removals from Task 4.
- Produces: user-facing upgrade note.

- [ ] **Step 1: Write the note**

```markdown
**BREAKING:** Search indexing of processes and subscriptions now happens automatically when a
process exits (completed, failed, aborted, suspended or awaiting callback) instead of in workflow
steps. The `refresh_subscription_search_index` and `refresh_process_search_index` steps have been
removed — delete any references to them from custom workflow step lists. Indexing failures are
logged and swallowed by default; set `SEARCH_INDEXING_STRICT=true` to have them raise.
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "Document breaking change for automatic process indexing"
```

---

## Verification Checklist

Before declaring the work complete:

- [ ] `grep -rn "refresh_subscription_search_index\|refresh_process_search_index" orchestrator/ test/` returns nothing
- [ ] `uv run pytest test/unit_tests -q` passes
- [ ] `uv run pytest test/integration_tests/services -q` passes
- [ ] `uv run mypy orchestrator` passes
- [ ] `pre-commit run --all-files` passes
- [ ] A failing workflow produces an indexed process (integration test proves it)
- [ ] The indexed process row carries its terminal status, not `running`
