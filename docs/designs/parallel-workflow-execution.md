# Design: Parallel Step Execution in the Workflow Engine

## 1. Problem Statement

All workflow steps currently execute sequentially via `_exec_steps()` which iterates a flat `StepList`. There is no way to express that certain steps are independent and could execute concurrently. This limits throughput for workflows that perform multiple independent external calls (e.g., provisioning two ports simultaneously).

## 2. Goals

- Enable parallel execution of independent steps within a workflow
- Extend the workflow DSL with fork/join semantics
- Remain **fully backwards compatible** — existing workflows, APIs, and database schema unchanged
- Handle errors, retries, and suspension in parallel branches
- Ensure the engine waits for all branches to complete before continuing sequentially

## 3. Design Overview

### 3.1 New DSL Syntax: `|` Operator and Dict Naming

Parallel execution is expressed using the `|` (pipe) operator between `StepList` branches, with an optional name via dict syntax. It is implemented as a special `step_group` variant — from the outside it looks like a single step.

#### Syntax A: Unnamed parallel (auto-generated name)

Use the `|` operator directly between branches:

```python
from orchestrator.workflow import step, begin, init, done, workflow

@step("Provision Port A")
def provision_port_a(subscription_id):
    return {"port_a": call_external_system_a(subscription_id)}

@step("Provision Port B")
def provision_port_b(subscription_id):
    return {"port_b": call_external_system_b(subscription_id)}

@step("Link Ports")
def link_ports(port_a, port_b):
    return {"link_id": create_link(port_a, port_b)}

@workflow("Create Dual Port", target=Target.CREATE)
def create_dual_port():
    return (
        init
        >> provision_initial_data
        >> (
            (begin >> provision_port_a)
            | (begin >> provision_port_b)
        )
        >> link_ports
        >> done
    )
```

#### Syntax B: Named parallel (dict syntax)

Wrap the `|` expression in a dict to provide a name for logging and UI:

```python
@workflow("Create Dual Port", target=Target.CREATE)
def create_dual_port():
    return (
        init
        >> provision_initial_data
        >> {
            "Provision both ports":
                (begin >> provision_port_a)
                | (begin >> provision_port_b)
        }
        >> link_ports
        >> done
    )
```

#### Syntax C: `parallel()` function (explicit, full control)

For advanced options like `retry_auth_callback`, a `parallel()` function is also available:

```python
from orchestrator.workflow import parallel

@workflow("Create Dual Port", target=Target.CREATE)
def create_dual_port():
    return (
        init
        >> parallel(
            "Provision both ports",
            begin >> provision_port_a,
            begin >> provision_port_b,
            retry_auth_callback=my_auth_callback,
        )
        >> link_ports
        >> done
    )
```

**Key properties:**
- The `|` operator on `StepList` creates a `ParallelStepList` — a container of branches
- `StepList.__rshift__` recognizes both `ParallelStepList` and `dict[str, ParallelStepList]`
- `parallel()` function remains available for advanced options
- Branches share the **same input state** (the state at the fork point)
- Branch results are **merged** into a single state at the join point
- Existing workflows that don't use `|` or `parallel()` are completely unaffected

### 3.2 Visual Representation

```
    ┌──────────────────────┐
    │   sequential steps   │
    └──────────┬───────────┘
               │
         ┌─────┴─────┐          FORK
         │           │
    ┌────▼────┐ ┌────▼────┐
    │branch 0 │ │branch 1 │     PARALLEL
    │ step_a  │ │ step_c  │
    │ step_b  │ │ step_d  │
    └────┬────┘ └────┬────┘
         │           │
         └─────┬─────┘          JOIN (barrier)
               │
    ┌──────────▼───────────┐
    │   sequential steps   │
    └──────────────────────┘
```

## 4. Detailed Design

### 4.1 New Process States

No new `ProcessStatus` or `StepStatus` values are needed. The parallel group uses existing states:

| Scenario | Branch states | Parallel group state |
|----------|--------------|---------------------|
| All succeed | All `Success` | `Success` (merged state) |
| One fails | Any `Failed` | `Failed` (first failure) |
| One waits (retry) | Any `Waiting` | `Waiting` |
| One suspends | Any `Suspend` | `Suspend` |
| Mix of success+waiting | Some done, some waiting | `Waiting` |

The parallel group itself is logged as a single step in `ProcessStepTable`, exactly like `step_group` today. Sub-step logging happens for each branch step individually (reusing the existing `step_group` sub-step logging mechanism).

### 4.2 State Management

#### Fork (input to branches)
Each branch receives a **deep copy** of the state at the fork point. This prevents race conditions between branches modifying shared state.

#### Join (merging branch results)
Branch results are merged left-to-right (branch 0 first, then branch 1, etc.):

```python
merged_state = {}
for branch_result in branch_results:
    merged_state.update(branch_result.unwrap())
```

**Conflict resolution:** Later branches overwrite earlier branches for the same key. This is by design — users must ensure branches write to distinct keys. A warning is logged if key conflicts are detected.

#### Reserved parallel metadata keys in state
```python
"__parallel_group": str        # Name of the parallel group (for resume)
"__parallel_branches": int     # Number of branches
"__parallel_branch_idx": int   # Current branch index (during execution)
"__parallel_results": dict     # Serialized branch results (for partial resume)
```

### 4.3 Execution Strategy

Parallel branches execute using `concurrent.futures.ThreadPoolExecutor` (already available in the codebase via the thread-based workflow execution). Each branch runs in its own thread, but all branches share the same database session scope (the parallel group acts as a single transaction boundary).

```python
def _exec_parallel_branches(
    branches: list[StepList],
    input_state: State,
    dblogstep: StepLogFuncInternal,
    name: str,
) -> Process:
    """Execute multiple branches concurrently and join their results."""
    branch_results: list[Process] = [None] * len(branches)

    def run_branch(idx: int, branch_steps: StepList) -> Process:
        branch_state = deepcopy(input_state)
        branch_state["__parallel_branch_idx"] = idx
        branch_process = Success(branch_state)
        return _exec_steps(branch_steps, branch_process, dblogstep)

    with ThreadPoolExecutor(max_workers=len(branches)) as executor:
        futures = {
            executor.submit(run_branch, idx, branch): idx
            for idx, branch in enumerate(branches)
        }
        for future in as_completed(futures):
            idx = futures[future]
            branch_results[idx] = future.result()

    return _join_results(branch_results, input_state, name)
```

#### Alternative: Sequential-parallel (simpler initial implementation)

For a simpler first implementation, branches can execute **sequentially** while still providing the fork/join semantics. This gives us the DSL and state management without threading complexity. Threading can be added later as an optimization.

```python
def _exec_parallel_branches_sequential(
    branches: list[StepList],
    input_state: State,
    dblogstep: StepLogFuncInternal,
    name: str,
) -> Process:
    """Execute branches sequentially (fork/join semantics without threading)."""
    branch_results: list[Process] = []
    for idx, branch_steps in enumerate(branches):
        branch_state = deepcopy(input_state)
        branch_state["__parallel_branch_idx"] = idx
        result = _exec_steps(branch_steps, Success(branch_state), dblogstep)
        branch_results.append(result)
    return _join_results(branch_results, input_state, name)
```

**Recommendation:** Start with sequential-parallel to validate the design, then add threading.

### 4.4 Join Logic

```python
def _join_results(
    branch_results: list[Process],
    input_state: State,
    name: str,
) -> Process:
    """Join branch results into a single Process.

    Priority order for non-success states:
    1. Failed — if any branch failed, the whole group fails
    2. Waiting — if any branch is waiting (retryable), the group waits
    3. Suspend — if any branch is suspended, the group suspends
    4. AwaitingCallback — if any branch awaits callback, the group awaits
    5. Success/Skipped — all branches succeeded, merge states
    """
    # Check for failures first
    failed = [r for r in branch_results if r.isfailed()]
    if failed:
        return failed[0]  # Return first failure

    # Check for waiting (retryable)
    waiting = [r for r in branch_results if r.iswaiting()]
    if waiting:
        return waiting[0]

    # Check for suspend
    suspended = [r for r in branch_results if r.issuspend()]
    if suspended:
        return suspended[0]

    # Check for awaiting callback
    awaiting = [r for r in branch_results if r.isawaitingcallback()]
    if awaiting:
        return awaiting[0]

    # All succeeded — merge states
    merged = deepcopy(input_state)
    conflicting_keys: set[str] = set()
    branch_keys: list[set[str]] = []

    for result in branch_results:
        result_state = result.unwrap()
        # Track keys for conflict detection (exclude internal keys)
        current_keys = {k for k in result_state if not k.startswith("__") and k not in input_state}
        for prev_keys in branch_keys:
            conflicting_keys |= current_keys & prev_keys
        branch_keys.append(current_keys)
        # Merge (later branches overwrite)
        merged.update(result_state)

    if conflicting_keys:
        logger.warning(
            "Parallel branches wrote to the same keys",
            parallel_group=name,
            conflicting_keys=conflicting_keys,
        )

    # Clean up internal parallel keys
    for key in ("__parallel_branch_idx",):
        merged.pop(key, None)

    return Success(merged)
```

### 4.5 Error Handling

#### Failure in one branch
When a branch fails, the parallel group reports `Failed`. The other branches that already completed successfully have their side effects committed (they ran in the same transaction scope). On retry, **all branches re-execute** (same semantics as `step_group` retry).

To enable partial retry (only re-execute failed branches), we store branch results in the state:

```python
"__parallel_results": {
    "0": {"status": "success", "state": {...}},
    "1": {"status": "failed", "error": {...}},
}
```

On resume, completed branches are skipped and only failed/waiting branches re-execute.

#### Retryable failure (Waiting)
If a branch returns `Waiting`, the parallel group returns `Waiting`. On retry, the engine resumes the parallel group. Completed branches are restored from `__parallel_results`, and only the waiting branch is re-executed.

#### Suspension (user input)
Parallel branches **should not contain `inputstep`s**. A `ValueError` is raised at workflow definition time if an `inputstep` is detected inside a `parallel()` block. This keeps the design simple — user interaction should happen before or after the parallel block.

If this restriction needs to be lifted later, it can be done by suspending the entire group and resuming the specific branch.

### 4.6 `ParallelStepList` and Operator Overloads

#### 4.6.1 `ParallelStepList` — The `|` Result Type

A new container type that holds the branches of a parallel block. Created by the `|` operator on `StepList`:

```python
class ParallelStepList:
    """Container for parallel branches, created by the | operator on StepList.

    >>> branch_a = begin >> step("A")(dict)
    >>> branch_b = begin >> step("B")(dict)
    >>> par = branch_a | branch_b
    >>> isinstance(par, ParallelStepList)
    True
    >>> len(par.branches)
    2

    Chaining | adds more branches:
    >>> branch_c = begin >> step("C")(dict)
    >>> par3 = par | branch_c
    >>> len(par3.branches)
    3
    """

    def __init__(self, branches: list[StepList]) -> None:
        if len(branches) < 2:
            raise ValueError("ParallelStepList requires at least 2 branches")
        self.branches = branches

    def __or__(self, other: StepList | ParallelStepList) -> ParallelStepList:
        """Add another branch: (a | b) | c == ParallelStepList([a, b, c])."""
        if isinstance(other, ParallelStepList):
            return ParallelStepList([*self.branches, *other.branches])
        if isinstance(other, StepList):
            return ParallelStepList([*self.branches, other])
        raise ValueError(f"Cannot use | with {type(other)}")

    def named(self, name: str) -> ParallelStepList:
        """Assign a name to this parallel block (alternative to dict syntax)."""
        self.name = name
        return self

    def __repr__(self) -> str:
        branch_strs = ", ".join(str(b) for b in self.branches)
        name = getattr(self, "name", None)
        if name:
            return f"ParallelStepList '{name}' [{branch_strs}]"
        return f"ParallelStepList [{branch_strs}]"
```

#### 4.6.2 `StepList.__or__` — Creating Parallel Branches

Add `__or__` to `StepList` to support the `|` operator:

```python
class StepList(list[Step]):
    # ... existing methods unchanged ...

    def __or__(self, other: StepList | ParallelStepList) -> ParallelStepList:
        """Create a parallel block: branch_a | branch_b.

        >>> a = begin >> step("A")(dict)
        >>> b = begin >> step("B")(dict)
        >>> par = a | b
        >>> len(par.branches)
        2

        Chaining works: a | b | c creates 3 branches.

        >>> c = begin >> step("C")(dict)
        >>> par3 = a | b | c
        >>> len(par3.branches)
        3
        """
        if isinstance(other, ParallelStepList):
            return ParallelStepList([self, *other.branches])
        if isinstance(other, StepList):
            return ParallelStepList([self, other])
        raise ValueError(f"Cannot use | with {type(other)}")
```

**Operator precedence note:** Python's `>>` binds tighter than `|`, so:
```python
begin >> step_a | begin >> step_b
# parses as:
(begin >> step_a) | (begin >> step_b)
```
This is exactly the grouping we want — each branch is fully built with `>>` before `|` combines them.

#### 4.6.3 `StepList.__rshift__` — Recognizing Parallel and Dict

Extend `__rshift__` to handle `ParallelStepList` and `dict[str, ParallelStepList]`:

```python
class StepList(list[Step]):
    def __rshift__(self, other: StepList | Step | ParallelStepList | dict) -> StepList:
        if isinstance(other, Step):
            return StepList([*self, other])

        if isinstance(other, StepList):
            return StepList([*self, *other])

        # Unnamed parallel: ... >> ((begin >> a) | (begin >> b)) >> ...
        if isinstance(other, ParallelStepList):
            name = getattr(other, "name", None) or _auto_parallel_name(other)
            par_step = _make_parallel_step(name, other.branches)
            return StepList([*self, par_step])

        # Named parallel via dict: ... >> {"Name": (begin >> a) | (begin >> b)} >> ...
        if isinstance(other, dict):
            if len(other) != 1:
                raise ValueError("Parallel dict must have exactly one key (the name)")
            name, value = next(iter(other.items()))
            if not isinstance(name, str):
                raise ValueError(f"Parallel dict key must be a string, got {type(name)}")
            if isinstance(value, ParallelStepList):
                par_step = _make_parallel_step(name, value.branches)
                return StepList([*self, par_step])
            if isinstance(value, list) and all(isinstance(v, StepList) for v in value):
                par_step = _make_parallel_step(name, value)
                return StepList([*self, par_step])
            raise ValueError(f"Parallel dict value must be ParallelStepList or list[StepList], got {type(value)}")

        if hasattr(other, "__name__"):
            raise ValueError(
                f"Expected @step decorated function or type Step or StepList, got {type(other)} "
                f"with name {other.__name__} instead."
            )
        raise ValueError(f"Expected @step decorated function or type Step or StepList, got {type(other)} instead.")


def _auto_parallel_name(par: ParallelStepList) -> str:
    """Generate an auto name from branch step names."""
    branch_names = []
    for branch in par.branches:
        names = [s.name for s in branch]
        branch_names.append(" + ".join(names) if names else "empty")
    return f"Parallel({', '.join(branch_names)})"
```

#### 4.6.4 The `parallel()` Function (Explicit API)

The `parallel()` function remains available for cases that need `retry_auth_callback` or other options:

```python
def parallel(
    name: str,
    *branches: StepList,
    retry_auth_callback: Authorizer | None = None,
    max_workers: int | None = None,
) -> Step:
    """Execute multiple step sequences in parallel.

    Each branch receives a deep copy of the current state. Branch results are merged
    left-to-right at the join point. Branches must write to distinct state keys.

    This function provides explicit control over parallel execution. For simpler cases,
    use the | operator syntax instead:

        # Using | operator (preferred for simple cases)
        init >> ((begin >> step_a) | (begin >> step_b)) >> done

        # Using | with dict naming
        init >> {"My parallel": (begin >> step_a) | (begin >> step_b)} >> done

        # Using parallel() for advanced options
        init >> parallel("My parallel", begin >> step_a, begin >> step_b,
                         retry_auth_callback=my_callback) >> done

    Args:
        name: Name for this parallel group (shown in logs/UI)
        *branches: Two or more StepList sequences to execute concurrently
        retry_auth_callback: Authorization callback for retrying on failure
        max_workers: Max concurrent threads (None = number of branches)

    Returns:
        A Step that can be composed with >> operator

    Raises:
        ValueError: If fewer than 2 branches provided
        ValueError: If any branch contains an inputstep
    """
    return _make_parallel_step(name, list(branches), retry_auth_callback=retry_auth_callback, max_workers=max_workers)
```

#### 4.6.5 The `_make_parallel_step()` Internal Function

Shared implementation used by both the `|` operator path and the `parallel()` function:

```python
def _make_parallel_step(
    name: str,
    branches: list[StepList],
    retry_auth_callback: Authorizer | None = None,
    max_workers: int | None = None,
) -> Step:
    """Create a parallel step from a list of branches (internal implementation)."""
    if len(branches) < 2:
        raise ValueError("parallel() requires at least 2 branches")

    # Validate no inputsteps in branches
    for branch_idx, branch in enumerate(branches):
        for s in branch:
            if s.form is not None:
                raise ValueError(
                    f"Parallel branches must not contain inputsteps. "
                    f"Found inputstep '{s.name}' in branch {branch_idx}."
                )

    def func(initial_state: State) -> Process:
        step_log_fn = step_log_fn_var.get()

        # Check for partial results from previous execution (resume)
        parallel_results = initial_state.pop("__parallel_results", None)

        def dblogstep(step_: Step, p: Process) -> Process:
            p = p.map(lambda s: s | {"__step_name_override": name, "__parallel_group": name})
            return step_log_fn(step_, p)

        if parallel_results:
            return _exec_parallel_resume(
                branches, initial_state, parallel_results, dblogstep, name, max_workers
            )

        return _exec_parallel_branches(
            branches, initial_state, dblogstep, name, max_workers
        )

    return make_step_function(func, name, retry_auth_callback=retry_auth_callback)
```

### 4.7 Database Impact

**No schema changes required.** The parallel group uses the existing `ProcessStepTable` structure:

- The parallel group is logged as a single step (like `step_group`)
- Individual branch steps are logged as sub-steps with `__step_name_override`
- Branch index is tracked via `__parallel_branch_idx` in the state

The `ProcessTable.last_step` field will show the parallel group name during execution.

### 4.8 API Impact

**No API changes required.** The parallel group is transparent to the REST/GraphQL API:

- Process status transitions work identically (RUNNING -> COMPLETED, RUNNING -> FAILED, etc.)
- Step logs show the parallel group and its sub-steps
- Resume/retry APIs work unchanged

## 5. Implementation Plan

### Phase 1: Core primitives (sequential execution)

1. **Add `ParallelStepList` class to `orchestrator/workflow.py`**
   - Container type for parallel branches
   - `__or__` for chaining: `par | branch_c`
   - `__repr__` for debugging

2. **Add `StepList.__or__` to `orchestrator/workflow.py`**
   - Creates `ParallelStepList` from two `StepList` branches
   - Supports chaining: `a | b | c` creates 3 branches

3. **Extend `StepList.__rshift__` to handle parallel types**
   - Accept `ParallelStepList` (unnamed parallel)
   - Accept `dict[str, ParallelStepList]` (named parallel)
   - Auto-generate name for unnamed parallel blocks
   - Validate dict has exactly one string key

4. **Add `_make_parallel_step()` internal function**
   - Shared implementation for `|` operator and `parallel()` function
   - Input validation (min 2 branches, no inputsteps)
   - Sequential branch execution (no threading)
   - State fork (deep copy) and join (merge)

5. **Add `_join_results()` to `orchestrator/workflow.py`**
   - Branch result aggregation
   - Priority-based status resolution
   - State merging with conflict detection

6. **Add `_exec_parallel_branches()` to `orchestrator/workflow.py`**
   - Sequential execution of branches
   - Per-branch state isolation
   - Sub-step logging

7. **Add `parallel()` function and export from `orchestrator/workflow.py`**
   - Explicit API for advanced options (`retry_auth_callback`, `max_workers`)
   - Delegates to `_make_parallel_step()`

### Phase 2: Resume and retry support

5. **Add `__parallel_results` state tracking**
   - Serialize completed branch results
   - Restore on resume
   - Skip completed branches on retry

6. **Add `_exec_parallel_resume()`**
   - Detect which branches need re-execution
   - Merge resumed results with stored results

### Phase 3: True parallel execution (optional)

7. **Add `ThreadPoolExecutor` execution mode**
   - Thread-safe state isolation
   - Thread-safe database logging
   - Configurable `max_workers`

### Phase 4: Documentation and examples

8. **Add example workflows**
9. **Update workflow documentation**

## 6. Test Design

### 6.1 Unit Tests (`test/unit_tests/test_parallel_workflow.py`)

```python
"""Tests for parallel step execution in the workflow engine."""
from copy import deepcopy
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest

from orchestrator.services.processes import SYSTEM_USER
from orchestrator.workflow import (
    Failed,
    ParallelStepList,
    Process,
    ProcessStat,
    Skipped,
    StepList,
    StepStatus,
    Success,
    Waiting,
    begin,
    conditional,
    done,
    init,
    inputstep,
    parallel,
    retrystep,
    step,
    step_group,
    workflow,
    runwf,
)
from pydantic_forms.core import FormPage
from orchestrator.config.assignee import Assignee
from test.unit_tests.test_workflow import create_new_process_stat, store
from test.unit_tests.workflows import (
    assert_complete,
    assert_failed,
    assert_state,
    assert_success,
    assert_waiting,
    extract_error,
)


# --- Step definitions for tests ---

@step("Branch A Step 1")
def branch_a_step1():
    return {"a1": "done"}


@step("Branch A Step 2")
def branch_a_step1_cont(a1):
    return {"a2": f"{a1}_continued"}


@step("Branch B Step 1")
def branch_b_step1():
    return {"b1": "done"}


@step("Branch B Step 2")
def branch_b_step1_cont(b1):
    return {"b2": f"{b1}_continued"}


@step("Sequential Before")
def seq_before():
    return {"before": True}


@step("Sequential After")
def seq_after(a1, b1, before):
    return {"after": True, "got_a1": a1, "got_b1": b1}


@retrystep("Retryable Branch Step")
def retryable_branch_step():
    raise ValueError("Retry me")


@step("Failing Branch Step")
def failing_branch_step():
    raise ValueError("Branch failed")


# --- Test: | operator and ParallelStepList ---

class TestPipeOperatorSyntax:
    """Test the | operator creates ParallelStepList correctly."""

    def test_pipe_creates_parallel_step_list(self):
        """StepList | StepList creates a ParallelStepList with 2 branches."""
        branch_a = begin >> branch_a_step1
        branch_b = begin >> branch_b_step1
        par = branch_a | branch_b

        assert isinstance(par, ParallelStepList)
        assert len(par.branches) == 2

    def test_pipe_chaining_creates_multiple_branches(self):
        """a | b | c creates a ParallelStepList with 3 branches."""
        branch_a = begin >> branch_a_step1
        branch_b = begin >> branch_b_step1

        @step("Branch C")
        def branch_c():
            return {"c1": "done"}

        par = branch_a | branch_b | (begin >> branch_c)
        assert isinstance(par, ParallelStepList)
        assert len(par.branches) == 3

    def test_pipe_operator_precedence_with_rshift(self):
        """>> binds tighter than |, so begin >> step_a | begin >> step_b works."""
        # This should parse as (begin >> branch_a_step1) | (begin >> branch_b_step1)
        par = begin >> branch_a_step1 | begin >> branch_b_step1

        assert isinstance(par, ParallelStepList)
        assert len(par.branches) == 2

    def test_unnamed_parallel_in_workflow(self):
        """| operator used directly in workflow definition with auto-generated name."""
        wf = workflow("Pipe WF")(
            lambda: init >> (
                (begin >> branch_a_step1)
                | (begin >> branch_b_step1)
            ) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["b1"] == "done"


class TestDictNamingSyntax:
    """Test the dict syntax for naming parallel blocks."""

    def test_dict_with_parallel_step_list(self):
        """{"name": branch_a | branch_b} creates a named parallel step."""
        wf = workflow("Dict WF")(
            lambda: init >> {
                "Provision ports":
                    (begin >> branch_a_step1)
                    | (begin >> branch_b_step1)
            } >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["b1"] == "done"

        # Verify the name appears in the log
        step_names = [entry[0] for entry in log]
        assert "Provision ports" in step_names

    def test_dict_with_list_of_steplists(self):
        """{"name": [branch_a, branch_b]} also works as alternative."""
        wf = workflow("Dict list WF")(
            lambda: init >> {
                "Provision ports": [
                    begin >> branch_a_step1,
                    begin >> branch_b_step1,
                ]
            } >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["b1"] == "done"

    def test_dict_with_multiple_keys_raises(self):
        """Dict with more than one key raises ValueError."""
        with pytest.raises(ValueError, match="exactly one key"):
            begin >> {"a": begin >> branch_a_step1 | begin >> branch_b_step1,
                       "b": begin >> branch_a_step1 | begin >> branch_b_step1}

    def test_dict_with_non_string_key_raises(self):
        """Dict with non-string key raises ValueError."""
        with pytest.raises(ValueError):
            begin >> {42: (begin >> branch_a_step1) | (begin >> branch_b_step1)}


# --- Test: Basic parallel execution (using all syntax variants) ---

class TestParallelBasicExecution:
    """Test basic fork/join semantics."""

    def test_two_branches_merge_state(self):
        """Two branches execute and their states are merged."""
        wf = workflow("Parallel WF")(
            lambda: init >> seq_before >> {
                "Parallel block":
                    (begin >> branch_a_step1)
                    | (begin >> branch_b_step1)
            } >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["before"] is True
        assert state["a1"] == "done"
        assert state["b1"] == "done"

    def test_multi_step_branches(self):
        """Branches with multiple steps each execute fully."""
        wf = workflow("Parallel WF")(
            lambda: init >> (
                (begin >> branch_a_step1 >> branch_a_step1_cont)
                | (begin >> branch_b_step1 >> branch_b_step1_cont)
            ) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["a2"] == "done_continued"
        assert state["b1"] == "done"
        assert state["b2"] == "done_continued"

    def test_three_branches(self):
        """Three or more branches work correctly."""
        @step("Branch C")
        def branch_c():
            return {"c1": "done"}

        wf = workflow("Triple WF")(
            lambda: init >> (
                (begin >> branch_a_step1)
                | (begin >> branch_b_step1)
                | (begin >> branch_c)
            ) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["b1"] == "done"
        assert state["c1"] == "done"

    def test_sequential_after_parallel_sees_merged_state(self):
        """Steps after parallel block can access merged state from all branches."""
        wf = workflow("Parallel WF")(
            lambda: init >> seq_before >> {
                "Parallel block":
                    (begin >> branch_a_step1)
                    | (begin >> branch_b_step1)
            } >> seq_after >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["after"] is True
        assert state["got_a1"] == "done"
        assert state["got_b1"] == "done"


class TestParallelStateIsolation:
    """Test that branches receive isolated state copies."""

    def test_branches_dont_see_each_others_mutations(self):
        """Each branch gets a deep copy of state; mutations don't leak."""
        @step("Mutate shared key A")
        def mutate_a(shared_list):
            return {"result_a": len(shared_list), "shared_list": [*shared_list, "a"]}

        @step("Mutate shared key B")
        def mutate_b(shared_list):
            return {"result_b": len(shared_list), "shared_list": [*shared_list, "b"]}

        wf = workflow("Isolation WF")(
            lambda: init >> (
                (begin >> mutate_a) | (begin >> mutate_b)
            ) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {"shared_list": [1, 2, 3]})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        # Both branches saw the original list of length 3
        assert state["result_a"] == 3
        assert state["result_b"] == 3
        # Branch B overwrites shared_list (last branch wins)
        assert state["shared_list"] == [1, 2, 3, "b"]


class TestParallelErrorHandling:
    """Test error handling in parallel branches."""

    def test_single_branch_failure_fails_group(self):
        """If one branch fails, the parallel group fails."""
        wf = workflow("Failing parallel WF")(
            lambda: init >> (
                (begin >> branch_a_step1) | (begin >> failing_branch_step)
            ) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_failed(result)
        assert extract_error(result) == "Branch failed"

    def test_retryable_branch_returns_waiting(self):
        """If one branch is retryable (Waiting), the parallel group returns Waiting."""
        wf = workflow("Retryable parallel WF")(
            lambda: init >> (
                (begin >> branch_a_step1) | (begin >> retryable_branch_step)
            ) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_waiting(result)

    def test_failure_takes_precedence_over_waiting(self):
        """Failed status takes precedence over Waiting."""
        wf = workflow("Mixed error WF")(
            lambda: init >> (
                (begin >> retryable_branch_step) | (begin >> failing_branch_step)
            ) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_failed(result)

    def test_steps_after_failed_parallel_not_executed(self):
        """Steps after a failed parallel block should not execute."""
        side_effects = []

        @step("Should not run")
        def should_not_run():
            side_effects.append("ran")
            return {}

        wf = workflow("WF")(
            lambda: init >> (
                (begin >> failing_branch_step) | (begin >> branch_a_step1)
            ) >> should_not_run >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_failed(result)
        assert side_effects == [], "Step after failed parallel should not execute"


class TestParallelValidation:
    """Test validation of parallel() arguments."""

    def test_requires_at_least_two_branches(self):
        """parallel() with fewer than 2 branches raises ValueError."""
        with pytest.raises(ValueError, match="at least 2 branches"):
            parallel("Single branch", begin >> branch_a_step1)

    def test_parallel_step_list_requires_two_branches(self):
        """ParallelStepList with fewer than 2 branches raises ValueError."""
        with pytest.raises(ValueError, match="at least 2 branches"):
            ParallelStepList([begin >> branch_a_step1])

    def test_rejects_inputsteps_in_branches_via_parallel(self):
        """parallel() branches must not contain inputsteps."""
        @inputstep("User Input", assignee=Assignee.SYSTEM)
        def user_input() -> type[FormPage]:
            class Form(FormPage):
                name: str
            return Form

        with pytest.raises(ValueError, match="must not contain inputsteps"):
            parallel(
                "Invalid parallel",
                begin >> branch_a_step1,
                begin >> user_input,
            )

    def test_rejects_inputsteps_in_branches_via_pipe(self):
        """| operator with inputsteps raises ValueError when composed with >>."""
        @inputstep("User Input", assignee=Assignee.SYSTEM)
        def user_input() -> type[FormPage]:
            class Form(FormPage):
                name: str
            return Form

        with pytest.raises(ValueError, match="must not contain inputsteps"):
            # Validation happens when >> converts ParallelStepList to a Step
            begin >> ((begin >> branch_a_step1) | (begin >> user_input))


class TestParallelWithConditional:
    """Test parallel blocks with conditional steps."""

    def test_conditional_step_in_branch(self):
        """Conditional steps inside branches work correctly."""
        skip_b = conditional(lambda s: False)

        wf = workflow("Conditional parallel WF")(
            lambda: init >> (
                (begin >> branch_a_step1) | skip_b(branch_b_step1)
            ) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"


class TestParallelComposition:
    """Test that parallel blocks compose with other workflow primitives."""

    def test_parallel_after_step_group(self):
        """Parallel block works after a step_group."""
        group = step_group("Group", begin >> branch_a_step1)

        @step("Independent C")
        def step_c():
            return {"c": True}

        wf = workflow("Composed WF")(
            lambda: init >> group >> (
                (begin >> branch_b_step1) | (begin >> step_c)
            ) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"  # from step_group
        assert state["b1"] == "done"  # from parallel branch 0
        assert state["c"] is True     # from parallel branch 1

    def test_multiple_parallel_blocks_in_sequence(self):
        """Multiple parallel blocks can appear in the same workflow."""
        @step("Step D")
        def step_d():
            return {"d": True}

        @step("Step E")
        def step_e():
            return {"e": True}

        wf = workflow("Multi parallel WF")(
            lambda: init
            >> ((begin >> branch_a_step1) | (begin >> branch_b_step1))
            >> ((begin >> step_d) | (begin >> step_e))
            >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["b1"] == "done"
        assert state["d"] is True
        assert state["e"] is True

    def test_parallel_function_still_works(self):
        """The explicit parallel() function continues to work for advanced use cases."""
        par = parallel("Explicit parallel", begin >> branch_a_step1, begin >> branch_b_step1)
        wf = workflow("Explicit WF")(lambda: init >> par >> done)

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["a1"] == "done"
        assert state["b1"] == "done"


class TestParallelBranchInputState:
    """Test that branches receive the correct input state."""

    def test_branches_receive_state_from_previous_step(self):
        """Each branch sees state produced by the step before the parallel block."""
        @step("Setup")
        def setup():
            return {"x": 42, "y": "hello"}

        @step("Use X")
        def use_x(x):
            return {"x_doubled": x * 2}

        @step("Use Y")
        def use_y(y):
            return {"y_upper": y.upper()}

        wf = workflow("Input state WF")(
            lambda: init >> setup >> (
                (begin >> use_x) | (begin >> use_y)
            ) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        state = result.unwrap()
        assert state["x_doubled"] == 84
        assert state["y_upper"] == "HELLO"


class TestParallelStepLogging:
    """Test that parallel execution produces correct step logs."""

    def test_named_parallel_group_appears_in_log(self):
        """A named parallel group appears with its name in the step log."""
        wf = workflow("Logging WF")(
            lambda: init >> {
                "My parallel block":
                    (begin >> branch_a_step1)
                    | (begin >> branch_b_step1)
            } >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        step_names = [entry[0] for entry in log]
        assert "Start" in step_names
        assert "My parallel block" in step_names
        assert "Done" in step_names

    def test_unnamed_parallel_gets_auto_name_in_log(self):
        """An unnamed parallel group gets an auto-generated name in the step log."""
        wf = workflow("Logging WF")(
            lambda: init >> (
                (begin >> branch_a_step1) | (begin >> branch_b_step1)
            ) >> done
        )

        log = []
        pstat = create_new_process_stat(wf, {})
        result = runwf(pstat, store(log))

        assert_complete(result)
        step_names = [entry[0] for entry in log]
        # Auto-generated name should contain the branch step names
        parallel_names = [n for n in step_names if "Parallel" in n or "Branch" in n]
        assert len(parallel_names) >= 1, f"Expected auto-named parallel step in log, got: {step_names}"
```

### 6.2 Test Categories

| Category | What it validates |
|----------|------------------|
| Pipe operator syntax | `\|` creates `ParallelStepList`, chaining, operator precedence |
| Dict naming syntax | `{"name": ...}` naming, list alternative, validation |
| Basic execution | Fork, execute, join, state merge (using all syntax variants) |
| State isolation | Branches get deep copies, no cross-branch mutation |
| Error handling | Failed/Waiting/Suspend propagation, precedence |
| Validation | Argument validation, inputstep rejection (both `\|` and `parallel()`) |
| Conditional | Conditional steps inside branches |
| Composition | With step_group, multiple parallel blocks, `parallel()` function |
| Input state | Branches see correct upstream state |
| Step logging | Named vs auto-named parallel groups in log |

### 6.3 Integration Tests

Integration tests should cover:

1. **Database persistence**: Parallel group steps are correctly stored in `ProcessStepTable`
2. **Resume after failure**: Workflow with failed parallel branch can be resumed
3. **Resume after waiting**: Workflow with waiting parallel branch can be retried
4. **API compatibility**: Existing process API endpoints work with parallel workflows
5. **WebSocket notifications**: Status changes during parallel execution broadcast correctly

## 7. Backwards Compatibility Checklist

| Aspect | Impact | Notes |
|--------|--------|-------|
| `StepList` class | Additive | New `__or__` method added; existing methods unchanged |
| `>>` operator | Extended | Now also accepts `ParallelStepList` and `dict`; existing behavior unchanged |
| `ProcessStatus` enum | None | No new values |
| `StepStatus` enum | None | No new values |
| `ProcessTable` schema | None | No new columns |
| `ProcessStepTable` schema | None | No new columns |
| `_exec_steps()` | None | Not modified |
| `runwf()` | None | Not modified |
| `step()` / `retrystep()` / `inputstep()` | None | Not modified |
| `step_group()` | None | Not modified |
| REST API | None | No new endpoints |
| GraphQL API | None | No schema changes |
| Existing workflows | None | No changes needed |

## 8. Future Enhancements

1. **True threading**: Replace sequential branch execution with `ThreadPoolExecutor`
2. **Nested parallelism**: Support `parallel()` inside `parallel()`
3. **Partial retry**: Only re-execute failed branches on resume
4. **Branch-level timeout**: Per-branch timeout with cancellation
5. **Dynamic branching**: Generate branches from state (e.g., one branch per subscription)
6. **Branch-scoped transactions**: Each branch in its own DB transaction for independent rollback
7. **inputstep support**: Allow user interaction within parallel branches (serialize/deserialize branch state)
8. **Progress tracking**: Report per-branch progress to UI via WebSocket

## 9. Open Questions

1. **Key conflicts**: Should we error on key conflicts, or just warn? (Recommendation: warn + log)
2. **Max branches**: Should we limit the number of branches? (Recommendation: no hard limit, but document performance implications)
3. **Thread safety**: When enabling true parallelism, how do we handle SQLAlchemy session safety? (Recommendation: each branch gets its own session from a scoped session factory)
4. **Abort during parallel**: If a user aborts while parallel branches are executing, how do we cancel in-flight branches? (Recommendation: check abort flag between steps, same as `global_lock` pattern)
