# Design: Parallel Step Execution in the Workflow Engine

## 1. Problem Statement

All workflow steps currently execute sequentially via `_exec_steps()` which iterates a flat `StepList`. There is no way to express that certain steps are independent and could execute concurrently. This limits throughput for workflows that perform multiple independent external calls (e.g., provisioning two ports simultaneously).

Two patterns are needed:

1. **Static parallel** — a fixed set of independent steplists known at definition time (e.g., always provision port A and port B together, or always trigger subworkflows X and Y).
2. **Dynamic parallel** — a variable number of steplists driven by a runtime iterable (e.g., trigger a subworkflow once per item in `state["ports"]`).

## 2. Goals

- Enable parallel execution of independent steplists within a workflow
- Extend the workflow DSL with fork/join semantics for both static and dynamic branching
- Store branch steps individually in the database with parent-child relationships via an association proxy
- Support both ThreadPool (in-process) and Celery (distributed) execution of parallel branches
- Handle errors, retries, and suspension in parallel branches
- Ensure the engine waits for all branches to complete before continuing sequentially
- **Do not merge branch state into the main workflow state** — branch results are persisted in the DB and accessible via `ProcessStepRelationTable` / `child_steps`

## 3. Design Overview

### 3.1 New DSL Syntax

Two complementary primitives cover both patterns.

#### 3.1.1 Static parallel: `|` Operator, Dict Naming, and `parallel()`

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
def link_ports(subscription_id):
    # Access branch results from DB, not from state
    return {"link_id": create_link(subscription_id)}

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

**Key properties (static parallel):**
- The `|` operator on `StepList` creates a `ParallelStepList` — a container of branches
- `StepList.__rshift__` recognizes both `ParallelStepList` and `dict[str, ParallelStepList]`
- `parallel()` function remains available for advanced options
- Branches share the **same input state** (the state at the fork point, deep-copied per branch)
- Branch results are **NOT merged** back into the main workflow state — they are persisted in the DB
- The step after the parallel block receives the **pre-parallel (initial) state**
- Existing workflows that don't use `|` or `parallel()` are completely unaffected

#### 3.1.2 Dynamic parallel: `foreach_parallel()`

`foreach_parallel` runs the **same branch template** once per item in a runtime list, with each item's data injected as the branch's seed state. The number of branches is not known until the workflow executes.

```python
from orchestrator.workflow import foreach_parallel

@step("Fetch ports")
def fetch_ports():
    return {"ports": [
        {"port_id": "p1", "vlan": 100},
        {"port_id": "p2", "vlan": 200},
    ]}

@step("Provision port")
def provision_port(port_id, vlan):          # injected from each item
    result = call_provisioning_api(port_id, vlan)
    return {f"port_{port_id}_result": result}

@step("Link ports")
def link_ports(ports):
    # Access branch results from DB via fork_step.child_steps
    return {"link_id": create_link(ports)}

@workflow("Provision N ports", target=Target.CREATE)
def provision_n_ports():
    return (
        init
        >> fetch_ports
        >> foreach_parallel("Provision ports", "ports", begin >> provision_port)
        >> link_ports
        >> done
    )
```

**Key properties (dynamic parallel):**
- The branch template (`StepList`) is defined at workflow definition time
- The number of branches and their seed states come from `state[items_key]` at runtime
- **Dict items**: each item dict is merged into the branch's initial state (`initial_state | item`)
- **Scalar items**: injected as `{"item": <value>, "item_index": <int>}`
- Branch results are **NOT merged** — they stay in the DB as child steps of the fork step
- An empty list returns `Success` with unchanged state (no threads spawned)

### 3.2 Visual Representation

**Static parallel** (`parallel()` / `|` operator) — fixed branches, defined at definition time:

```
    ┌──────────────────────┐
    │   sequential steps   │
    └──────────┬───────────┘
               │
         ┌─────┴─────┐          FORK (static — 2 branches)
         │           │
    ┌────▼────┐ ┌────▼────┐
    │branch 0 │ │branch 1 │     PARALLEL (each gets deep copy of state)
    │ step_a  │ │ step_c  │
    │ step_b  │ │ step_d  │
    └────┬────┘ └────┬────┘
         │           │          Results persisted in DB (not merged)
         └─────┬─────┘          JOIN (barrier — worst status wins)
               │
    ┌──────────▼───────────┐
    │   sequential steps   │    Receives pre-parallel state
    └──────────────────────┘
```

**Dynamic parallel** (`foreach_parallel()`) — N branches from a runtime list:

```
    ┌──────────────────────┐
    │   sequential steps   │
    │  (produces items=[…])│
    └──────────┬───────────┘
               │  items = [item_0, item_1, …, item_N-1]
      ┌────────┼────────┐       FORK (dynamic — N branches)
      │        │        │
 ┌────▼──┐ ┌───▼──┐ ┌───▼──┐
 │item_0 │ │item_1│ │item_N│   PARALLEL (same branch template)
 │ seed  │ │ seed │ │ seed │   each seeded with its item
 └────┬──┘ └───┬──┘ └───┬──┘
      │        │        │       Results persisted in DB (not merged)
      └────────┼────────┘       JOIN (barrier — worst status wins)
               │
    ┌──────────▼───────────┐
    │   sequential steps   │    Receives pre-parallel state
    └──────────────────────┘
```

## 4. Detailed Design

### 4.1 New Process States

No new `ProcessStatus` or `StepStatus` values are needed. The parallel group uses existing states:

| Scenario | Branch states | Parallel group state |
|----------|--------------|---------------------|
| All succeed | All `Success` | `Success` (pre-parallel state) |
| One fails | Any `Failed` | `Failed` (first failure by priority) |
| One waits (retry) | Any `Waiting` | `Waiting` |
| One suspends | Any `Suspend` | `Suspend` |
| Mix of success+waiting | Some done, some waiting | `Waiting` |

The parallel group creates a **fork step** in `ProcessStepTable` that acts as the parent. Each branch writes its own `ProcessStepTable` rows, linked to the fork step via `ProcessStepRelationTable` (see section 4.8). Each branch thread gets its own DB session via `db.database_scope()`.

### 4.2 State Management

#### Fork (input to branches)
Each branch receives a **deep copy** of the state at the fork point. This prevents race conditions between branches modifying shared state.

For `foreach_parallel`, the deep copy is further enriched with the item's seed data before the branch runs:

```python
branch_state = deepcopy(initial_state)
branch_state.update(seed)   # seed = item dict, or {"item": value, "item_index": idx}
```

#### Join (no merge — worst status wins)

Branch results are **NOT merged** back into the main workflow state. Instead:

1. `_worst_status` scans all branch results for the worst non-success status
2. If any branch failed/waiting/suspended, the parallel group returns that status
3. If all branches succeeded, the group returns `Success(initial_state)` — the **pre-parallel state**

Branch result data is accessible from the DB via `fork_step.child_steps` (an `association_proxy` through `ProcessStepRelationTable`).

```python
_STATUS_PRIORITY = ["isfailed", "iswaiting", "issuspend", "isawaitingcallback"]

def _worst_status(branch_results: list[Process]) -> Process | None:
    """Return the branch with the worst non-success status, or None if all succeeded."""
    return next(
        (result for check in _STATUS_PRIORITY for result in branch_results if getattr(result, check)()),
        None,
    )
```

All parallel tracking — branch results, completion counts, branch-to-fork relationships — is stored in the database (see section 4.8), not in workflow state.

### 4.3 Execution Strategy

The execution strategy is determined by the global `app_settings.EXECUTOR` setting. The engine dispatches to the appropriate executor at the fork point:

```python
def _exec_parallel_branches(branches, initial_state, name, max_workers=None, seeds=None):
    pstat = process_stat_var.get(None)
    process_id = pstat.process_id if pstat else None
    n_branches = len(seeds) if seeds else len(branches)

    fork_step_id = _create_fork_step(...) if process_id else None

    match app_settings.EXECUTOR:
        case ExecutorType.WORKER if process_id is not None and fork_step_id is not None:
            return _dispatch_worker_branches(branches, initial_state, process_id, ...)
        case _:
            return _run_threadpool_branches(branches, initial_state, name, ...)
```

Both paths share the same setup:

1. Create a **fork step** in `ProcessStepTable` (with `parallel_total_branches` set) via `database_scope()`
2. Each branch writes its own `ProcessStepTable` rows via `_make_branch_dblogstep`
3. Branch steps are linked to the fork step via `ProcessStepRelationTable`
4. After all branches complete, `_worst_status` determines the group outcome

#### 4.3.1 `transactional` Wrapping

Both `_make_parallel_step` and `foreach_parallel` wrap their execution in `transactional(db, logger)`. This ensures:
- `disable_commit` is active on the main session during parallel execution
- Fork step creation and updates use `database_scope()` to bypass `disable_commit` (separate connection)
- Branch threads get their own sessions via `database_scope()` (not affected by `disable_commit`)
- On success, `transactional` commits the main session
- On failure, `transactional` rolls back

```python
def _make_parallel_step(name, branches, ...):
    def func(initial_state):
        with transactional(db, logger):
            return _exec_parallel_branches(branches, initial_state, name, ...)
    ...
```

#### 4.3.2 ThreadPool Execution

Each branch runs in its own thread with its own database session (via `database_scope()`). Branch steps are logged individually to the DB.

```python
def _run_threadpool_branches(branches, initial_state, name, process_id,
                             fork_step_id, current_user, max_workers=None, seeds=None):
    n_branches = len(seeds) if seeds else len(branches)
    workers = max_workers if max_workers is not None else n_branches
    branch_results = [None] * n_branches

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_run_branch, branch, initial_state,
                            process_id=process_id, parent_step_id=fork_step_id,
                            branch_index=idx, current_user=current_user,
                            state_seed=seeds[idx] if seeds else None): idx
            for idx, branch in ...
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                branch_results[idx] = future.result()
            except Exception as e:
                branch_results[idx] = Failed(error_state_to_dict(e))

    results = [r for r in branch_results if r is not None]
    worst = _worst_status(results)

    if fork_step_id is not None:
        fork_status = worst.status if worst is not None else StepStatus.SUCCESS
        _update_fork_step(fork_step_id, fork_status, initial_state, n_branches)

    if worst is not None:
        return worst

    return Success(initial_state | {"__replace_last_state": True, ...})
```

#### Fork Step Creation with `database_scope()`

The fork step must be visible to branch threads before they start. Since branch threads get their own connections from the pool, the fork step must be committed to the DB independently of the caller's transaction (which may have `disable_commit` active from `transactional`).

`_create_fork_step` uses a separate `database_scope()` session to commit the fork step on its own connection:

```python
def _create_fork_step(process_id, name, initial_state, total_branches, current_user):
    with db.database_scope():
        fork_step = ProcessStepTable(
            process_id=process_id,
            name=name,
            status=StepStatus.SUCCESS,
            state=initial_state,
            created_by=current_user,
            parallel_total_branches=total_branches,
            parallel_completed_count=0,
        )
        db.session.add(fork_step)
        db.session.commit()
        return fork_step.step_id
```

Similarly, `_update_fork_step` uses `database_scope()` to commit the status update:

```python
def _update_fork_step(fork_step_id, status, state, n_branches):
    with db.database_scope():
        stmt = (
            update(ProcessStepTable)
            .where(ProcessStepTable.step_id == fork_step_id)
            .values(status=status, state=state, parallel_completed_count=n_branches)
        )
        db.session.execute(stmt)
        db.session.commit()
```

#### Per-branch DB Logging

Each branch gets its own DB session via `db.database_scope()` and a dedicated step logger that writes real `ProcessStepTable` rows linked to the parent fork step:

```python
def _make_branch_dblogstep(process_id, parent_step_id, branch_index, current_user, seed_state=None):
    order_counter = itertools.count()

    def branch_dblogstep(step_, p):
        child_step = ProcessStepTable(
            process_id=process_id,
            name=f"[Branch {branch_index}] {step_name}",
            status=p.status,
            state=step_state,
            created_by=current_user,
        )
        db.session.add(child_step)
        db.session.flush()

        order_id = next(order_counter)
        relation = ProcessStepRelationTable(
            parent_step_id=parent_step_id,
            child_step_id=child_step.step_id,
            order_id=order_id,
            branch_index=branch_index,
            seed_state=seed_state if order_id == 0 else None,
        )
        db.session.add(relation)
        db.session.commit()
        return p.__class__(child_step.state)

    return branch_dblogstep
```

The `_run_branch` function uses this logger:

```python
def _run_branch(branch, initial_state, *, process_id, parent_step_id, branch_index,
                current_user, state_seed=None):
    with db.database_scope():
        branch_state = deepcopy(initial_state)
        if state_seed is not None:
            branch_state.update(state_seed)

        branch_logstep = (
            _make_branch_dblogstep(process_id, parent_step_id, branch_index, current_user, seed_state=state_seed)
            if process_id is not None and parent_step_id is not None
            else lambda step_, p: p
        )
        return _exec_steps(branch, Success(branch_state), branch_logstep)
```

#### DB Session Isolation via `db.database_scope()`

The `Database` class uses `ContextVar`-scoped sessions. Each branch thread calls `db.database_scope()` to create a new UUID token, giving it an isolated session with its own connection from the pool.

#### Thread Safety Analysis

| Resource | Thread-safe? | Why |
|----------|-------------|-----|
| `db.session` | YES (with `database_scope`) | Each thread creates own ContextVar scope, own session, own connection |
| `step_log_fn_var` | YES | Inherited from parent, read-only in branches |
| `ProcessStepTable` writes | YES | Each branch writes to different rows on its own connection |
| `ProcessStepRelationTable` writes | YES | Each branch writes its own relation rows on its own connection |
| Fork step | YES | Created before threads start via separate `database_scope()` |
| `_worst_status` | YES | Runs in parent thread after all branches complete |

#### 4.3.3 Celery Execution (Branch-as-Task)

When `EXECUTOR == ExecutorType.WORKER`, parallel branches are submitted as Celery tasks. Each branch steplist runs to completion on a Celery worker. The parent workflow suspends until all branches finish.

```python
def _dispatch_worker_branches(branches, initial_state, process_id,
                               current_user, fork_step_id, is_task, seeds=None):
    task_name = EXECUTE_PARALLEL_BRANCH if is_task else EXECUTE_PARALLEL_BRANCH_WORKFLOW
    trigger_task = get_celery_task(task_name)

    for idx, _ in enumerate(branches):
        branch_initial = (initial_state | seeds[idx]) if seeds else initial_state
        seed = seeds[idx] if seeds else None
        trigger_task.delay(process_id, idx, fork_step_id, branch_initial, current_user, seed)

    return Waiting(initial_state | {"__parallel_waiting": True, "__fork_step_id": str(fork_step_id)})
```

#### Step Serialization for Celery

Steps are Python functions and cannot be serialized. The Celery task receives `process_id + fork_step_id + branch_index` and reconstructs the branch steplist on the worker by looking up the workflow from DB:

```python
def _resolve_branch_from_db(fork_step_id, process_id, branch_index):
    fork_step = db.session.get(ProcessStepTable, fork_step_id)
    parallel_group_name = fork_step.name

    process = db.session.get(ProcessTable, process_id)
    workflow_key = process.workflow.name
    wf = get_workflow(workflow_key)

    parallel_step = next(
        s for s in wf.steps if getattr(s, '_parallel_group_name', None) == parallel_group_name
    )
    return parallel_group_name, reconstruct_branch(parallel_step, branch_index)
```

#### Atomic Join: DB-based `UPDATE...RETURNING`

When a branch Celery task completes, it atomically increments the fork step's completion counter:

```python
def _atomic_increment_completed(fork_step_id):
    stmt = (
        update(ProcessStepTable)
        .where(ProcessStepTable.step_id == fork_step_id)
        .values(parallel_completed_count=ProcessStepTable.parallel_completed_count + 1)
        .returning(ProcessStepTable.parallel_completed_count, ProcessStepTable.parallel_total_branches)
    )
    result = db.session.execute(stmt)
    completed, total = result.one()
    db.session.commit()
    return completed, total
```

#### Last-Finisher Continuation

The last branch to complete detects this via the atomic counter and triggers the join:

```python
completed, total = _atomic_increment_completed(fork_step_id)

if total is not None and completed >= total:
    _join_and_resume(process_id=process_id, fork_step_id=fork_step_id,
                     initial_state=initial_state, user=user)
```

`_join_and_resume` loads all child steps from `ProcessStepRelationTable`, determines the worst status across all branches, updates the fork step, and resumes the parent workflow via `get_execution_context()["resume"]`, respecting the configured executor.

### 4.4 Error Handling

#### Failure in one branch
When a branch fails, the parallel group reports `Failed`. Since each branch writes its own `ProcessStepTable` rows, the DB contains a complete record of which branches succeeded and which failed.

#### Retryable failure (Waiting)
If a branch returns `Waiting`, the parallel group returns `Waiting`. On retry, the engine queries the fork step's child relations to determine which branches completed successfully.

#### Status priority
`_worst_status` checks branch results in priority order: `Failed > Waiting > Suspend > AwaitingCallback > Success`. The first non-success result found (in priority order) becomes the group's result.

#### Disallowed step types in parallel branches
Parallel branches **must not contain `inputstep`s or `callback_step`s**. Both are validated at workflow definition time:

- `inputstep`: Detected via `s.form is not None`
- `callback_step`: Detected via `getattr(s, '_is_callback_step', False)`

A `ValueError` is raised if either is found inside a `parallel()` block.

### 4.5 `ParallelStepList` and Operator Overloads

#### 4.5.1 `ParallelStepList` — The `|` Result Type

A new container type that holds the branches of a parallel block. Created by the `|` operator on `StepList`:

```python
class ParallelStepList:
    def __init__(self, branches: list[StepList]) -> None:
        if len(branches) < 2:
            raise ValueError("ParallelStepList requires at least 2 branches")
        self.branches = branches

    def __or__(self, other: StepList | ParallelStepList) -> ParallelStepList:
        if isinstance(other, ParallelStepList):
            return ParallelStepList([*self.branches, *other.branches])
        if isinstance(other, StepList):
            return ParallelStepList([*self.branches, other])
        raise ValueError(f"Cannot use | with {type(other)}")
```

#### 4.5.2 `StepList.__or__` — Creating Parallel Branches

```python
class StepList(list[Step]):
    def __or__(self, other: StepList | ParallelStepList) -> ParallelStepList:
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

#### 4.5.3 `StepList.__rshift__` — Recognizing Parallel and Dict

`__rshift__` handles `ParallelStepList` and `dict[str, ParallelStepList]` by calling `_make_parallel_step` to create a single `Step` that encapsulates the parallel execution.

### 4.6 `foreach_parallel` — Internal Design

`foreach_parallel` is built on the same infrastructure as `parallel`, wrapped in `transactional`:

```python
def foreach_parallel(name, items_key, branch, max_workers=None):
    def func(initial_state):
        with transactional(db, logger):
            raw = initial_state.get(items_key)
            if raw is None:
                raise ValueError(f"foreach_parallel: key '{items_key}' not found in state")
            items = list(raw)
            if not items:
                return Success(initial_state)

            seeds = [
                item if isinstance(item, dict) else {"item": item, "item_index": idx}
                for idx, item in enumerate(items)
            ]
            return _exec_parallel_branches([branch], initial_state, name,
                                           max_workers=max_workers, seeds=seeds)

    step_fn = make_step_function(func, name)
    step_fn._foreach_branch_template = branch
    step_fn._parallel_group_name = name
    return step_fn
```

#### State seeding rules

| Item type | Keys injected into branch state |
|---|---|
| `dict` | All keys in the dict: `{"port_id": "p1", "vlan": 100}` → branch sees `port_id` and `vlan` |
| Non-dict (scalar, etc.) | `{"item": <value>, "item_index": <int>}` |

#### Empty list behaviour

If `state[items_key]` is an empty list, `foreach_parallel` immediately returns `Success(initial_state)` — no threads are created.

### 4.7 Database Impact

#### New table: `process_step_relations`

A join table linking parent (fork) steps to child (branch) steps:

```python
class ProcessStepRelationTable(BaseModel):
    __tablename__ = "process_step_relations"

    parent_step_id = mapped_column(UUIDType, ForeignKey("process_steps.stepid", ondelete="CASCADE"), primary_key=True)
    child_step_id = mapped_column(UUIDType, ForeignKey("process_steps.stepid", ondelete="CASCADE"), primary_key=True)
    order_id = mapped_column(Integer(), primary_key=True)
    branch_index = mapped_column(Integer(), nullable=False)
    seed_state = mapped_column(pg.JSONB(none_as_null=True), nullable=True)

    parent_step = relationship("ProcessStepTable", back_populates="child_step_relations", foreign_keys=[parent_step_id])
    child_step = relationship("ProcessStepTable", back_populates="parent_step_relations", foreign_keys=[child_step_id])
```

#### New columns on `ProcessStepTable`

```python
class ProcessStepTable(BaseModel):
    # ... existing columns ...
    parallel_total_branches = mapped_column(Integer(), nullable=True)
    parallel_completed_count = mapped_column(Integer(), nullable=True, server_default=text("0"))

    child_step_relations = relationship("ProcessStepRelationTable", cascade="all, delete-orphan", ...)
    parent_step_relations = relationship("ProcessStepRelationTable", cascade="all, delete-orphan", ...)
    child_steps = association_proxy("child_step_relations", "child_step")
```

#### Visual: DB structure for a parallel workflow

```
ProcessTable (pid=abc)
├── ProcessStepTable (step_id=s1, name="Start", status="success")
├── ProcessStepTable (step_id=s2, name="Provision ports", status="success",    ← fork step
│                      parallel_total_branches=2, parallel_completed_count=2)
│   ├── ProcessStepRelationTable (parent=s2, child=s3, order_id=0, branch_index=0)
│   ├── ProcessStepRelationTable (parent=s2, child=s4, order_id=0, branch_index=1)
│   │
│   ├── ProcessStepTable (step_id=s3, name="[Branch 0] Provision Port A", status="success")
│   └── ProcessStepTable (step_id=s4, name="[Branch 1] Provision Port B", status="success")
│
└── ProcessStepTable (step_id=s5, name="Link Ports", status="success")
```

#### Migration

```python
def upgrade() -> None:
    op.add_column("process_steps", sa.Column("parallel_total_branches", sa.Integer(), nullable=True))
    op.add_column("process_steps", sa.Column("parallel_completed_count", sa.Integer(), nullable=True,
                                              server_default=sa.text("0")))
    op.create_table(
        "process_step_relations",
        sa.Column("parent_step_id", UUIDType(), sa.ForeignKey("process_steps.stepid", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("child_step_id", UUIDType(), sa.ForeignKey("process_steps.stepid", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("order_id", sa.Integer(), primary_key=True),
        sa.Column("branch_index", sa.Integer(), nullable=False),
        sa.Column("seed_state", pg.JSONB(none_as_null=True), nullable=True),
    )

def downgrade() -> None:
    op.drop_table("process_step_relations")
    op.drop_column("process_steps", "parallel_completed_count")
    op.drop_column("process_steps", "parallel_total_branches")
```

### 4.8 API Impact

**No API endpoint changes required.** The parallel group is transparent to the REST/GraphQL API:

- Process status transitions work identically
- Step logs now include per-branch step rows, giving finer-grained visibility
- The `ProcessStepRelationTable` enables UI to render parallel branches as a tree
- `enrich_step_details` in `orchestrator/utils/enrich_process.py` recursively serializes `child_steps` for fork steps
- Resume/retry APIs work unchanged

## 5. Key Implementation Files

| File | Purpose |
|------|---------|
| `orchestrator/workflow.py` | Core parallel engine: `_make_parallel_step`, `_exec_parallel_branches`, `_run_threadpool_branches`, `_dispatch_worker_branches`, `_run_branch`, `_create_fork_step`, `_update_fork_step`, `_worst_status`, `_make_branch_dblogstep`, `reconstruct_branch`, `parallel()`, `foreach_parallel()`, `ParallelStepList` |
| `orchestrator/services/parallel.py` | Celery worker branch execution: `run_worker_branch`, `_atomic_increment_completed`, `_collect_branch_results`, `_resolve_branch_from_db`, `_join_and_resume` |
| `orchestrator/db/models.py` | `ProcessStepTable` (parallel columns), `ProcessStepRelationTable` |
| `orchestrator/utils/enrich_process.py` | `enrich_step_details` — recursive serialization of fork + child steps for API |
| `orchestrator/settings.py` | `ExecutorType` enum, `EXECUTOR` setting |
| `test/unit_tests/test_parallel_workflow.py` | 40 unit tests covering DSL syntax, execution, state isolation, error handling, composition, threading, foreach_parallel |
| `test/unit_tests/test_parallel_celery.py` | Unit tests for reconstruct_branch, executor dispatch, worker branch dispatch, atomic increment |

## 6. Backwards Compatibility

| Aspect | Impact | Notes |
|--------|--------|-------|
| `StepList` class | Additive | New `__or__` method added; existing methods unchanged |
| `>>` operator | Extended | Now also accepts `ParallelStepList` and `dict`; existing behavior unchanged |
| `ProcessStepTable` schema | Additive | Two new nullable columns; existing rows unaffected |
| `ProcessStepRelationTable` | New | New table; no impact on existing data |
| `parallel()` / `foreach_parallel()` | New | New functions; no changes to existing workflows |
| REST/GraphQL API | None | No new endpoints; step logs now include branch detail rows |
| Existing workflows | None | No changes needed |

## 7. Future Enhancements

1. **Branch-level timeout**: Per-branch timeout with cancellation
2. **Partial retry**: Re-execute only failed branches on retry (query `ProcessStepRelationTable`)
3. **inputstep/callback support**: Allow user interaction within parallel branches
4. **UI tree rendering**: Use `ProcessStepRelationTable` to render parallel branches as a tree in the UI
5. **Abort during parallel**: Check abort flag between steps in branches

## 8. Resolved Questions

1. **State merging**: Branch results are NOT merged — they stay in DB. Post-parallel steps receive pre-parallel state.
2. **Max branches**: No hard limit; `max_workers` parameter controls thread pool size
3. **Thread safety**: Each branch gets its own session + connection via `db.database_scope()`
4. **Fork step visibility**: Created via separate `database_scope()` with real commit, visible to branch threads
5. **Celery step serialization**: Reference by `workflow_key + parallel_group_name + branch_index`; reconstruct on worker
6. **Join detection**: DB-based atomic counter via `UPDATE...RETURNING` on `ProcessStepTable`
7. **Callback steps in branches**: Disallowed alongside inputsteps; validated at definition time
8. **`transactional` compatibility**: Fork step and update use `database_scope()` to bypass `disable_commit`
