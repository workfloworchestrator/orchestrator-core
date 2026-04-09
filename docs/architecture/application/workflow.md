# What is a workflow and how does it work?

The workflow engine is the core of the software, it has been created to execute a number of functions.

- Safely and reliable manipulate customer `Subscriptions` from one state to the next and maintain auditability.
- Create an API through which programmatically `Subscriptions` can be manipulated.
- Execute step functions in order and allow the retry of previously failed process-steps in an idempotent way.
- Atomically execute workflow functions.

## Best Practices

The orchestrator will always attempt to be as robust as possible when executing workflow steps.
However, it is always up to the developer to implement the best practices as well as they can.

### Safeguards in the orchestrator;

- **Atomic Step Execution**: Each step is treated as an atomic unit.
  If a step fails, no partial changes are committed to the database.
  Because of this, calling .commit() on the ORM within a step function is not allowed.
- **`insync` Subscription Requirement**: By default, workflows can only run on subscriptions that are marked as `insync`, unless explicitly configured otherwise.
  This prevents multiple workflows from manipulating the same subscription concurrently.
  One of the first actions a workflow should perform is to mark the subscription as `out of sync` to avoid conflicts.
- **Step Retry Behavior**: Failed steps can be retried indefinitely. Each retry starts from the state of the **last successfully completed** step.


### Coding gotchas

- The orchestrator is best suited to be used as a data manipulator, not as a data transporter.
  - Use the State log as a log of work, not a log of data.
  - If the data you enter in the state is corrupt or wrong, you might need a difficult database query to update the state to resolve the conflict.
- Always retrieve external data at the moment it's needed during a step, not earlier.
  This increases the robustness of the step.
- Each step function should perform a single, clearly defined unit of work.
  Theoretically you can execute the whole workflow in a single step, However this does not help with traceability and reliability.


## Workflows

> [explanation to create a workflow in code](../../getting-started/workflows.md)

Workflows are composed of one or more **steps**, each representing a discrete unit of work in the subscription management process.
Steps are executed sequentially by the workflow engine and are the fundamental building blocks of workflows.

There are two high-level kinds of workflows:

- workflows
    - Defined for specific products.
    - Perform operations like creating, modifying, or terminating subscriptions.
- tasks
    - Not tied to a specific product and may not involve a subscription at all.
    - Can be scheduled to run periodically or triggered manually.
    - Useful for actions like cleanup jobs or triggering validations across multiple subscriptions.
    - Examples can be found in `orchestrator.workflows.tasks`.

Workflows and tasks need to be registered in the database and initialized as a `LazyWorkflowInstance` to work, see [registering workflows] for more info.

### Subscription Workflow Types

Workflows are categorized based on the operations they perform on a subscription:

- Create ([create_workflow])
    - The "base" workflow that initializes a new subscription for the product.
    - Only one create workflow should exist per product.
- Modify ([modify_workflow])
    - Modify an existing subscription (e.g., updating parameters, migrating to another product).
    - Multiple modify workflows can exist, each handling a specific type of modification.
- Terminate ([terminate_workflow])
    - Terminates the subscription and removes its data and references from external systems.
    - External references should only be retained if they also hold historical records.
    - Only one terminate workflow should exist per product.
- Validate ([validate_workflow])
    - Verifies that external systems are consistent with the orchestrator's subscription state.
    - Only one validate workflow should exist per product.
- Reconcile ([reconcile_workflow])
    - Ensures that the orchestrator's subscription state is in sync with external systems.
    - Only one reconcile workflow should exist per product.



### Default Workflows

Registering a _Default Workflow_ attaches a given workflow to all Products.
To ensure this, modify the `DEFAULT_PRODUCT_WORKFLOWS` environment variable and add the workflow the database with a migration.

By default, `DEFAULT_PRODUCT_WORKFLOWS` is set to `['modify_note']`.

More about registering workflows can be found [here][registering-workflows].

### Tasks

Tasks are workflows that aren't associated with any subscriptions, and can be run by the Orchestrator's scheduler.
Learn about tasks and scheduling [here][tasks-and-scheduling].

## Workflow Steps

Workflows are composed of one or more **steps**, where each step is executed sequentially by the workflow engine and are the fundamental building blocks of workflows.

### Step Characteristics

- **Atomicity**: Each step is atomic, either it fully completes or has no effect. This ensures data consistency and reliable state transitions.
- **Idempotency**: Steps should be designed to be safely repeatable without causing unintended side effects.
- **Traceability**: By breaking workflows into fine-grained steps, the orchestrator maintains clear audit trails and simplifies error handling and retries.

### Types of Steps

The orchestrator supports several kinds of steps to cover different use cases:

- **`step`** [functional docs for step]  
  Executes specific business logic or external API calls as part of the subscription process.

- **`retrystep`** [functional docs for retrystep]  
  Similar to `step`, but designed for operations that may fail intermittently. These steps will automatically be retried periodically on failure.

- **`inputstep`** [functional docs for inputstep]  
  Pauses the workflow to request and receive user input during execution.

- **`conditional`** [functional docs for conditional]  
  Conditionally executes the step based on environment variables or process state.  
  If the condition evaluates to false, the step is skipped entirely.

- **`callback_step`** [functional docs for callback_step]  
  Pauses workflow execution while waiting for a external event to complete.

For a practical example of how to define reusable workflow steps—and how to leverage singledispatch for type-specific logic—see:
👉 [Reusable step functions and singledispatch usage]


### Parallel Steps

The workflow engine supports two kinds of parallel execution, both implemented as a fork/join pattern: the engine forks the state into isolated copies for each branch, executes them concurrently, and joins the results back into a single state.

Parallel execution supports two backends:

- **ThreadPool** (default): Branches run in-process using a `ThreadPoolExecutor`. Each branch thread gets its own database session via `db.database_scope()`.
- **Celery** (distributed): When `EXECUTOR=celery`, each branch is submitted as a separate Celery task. The parent workflow suspends (`Waiting`) until all branches complete. The last branch to finish atomically detects completion and resumes the parent workflow.

#### Static parallel — fixed branches

Use when the set of branches is known at definition time (e.g., always provision port A and port B together).

**Pipe operator (unnamed)**:
```python
@create_workflow(...)
def create_dual_port():
    return init >> (
        (begin >> provision_port_a)
        | (begin >> provision_port_b)
    ) >> link_ports >> done
```

**Dict naming (named)**:
```python
@create_workflow(...)
def create_dual_port():
    return init >> {
        "Provision ports": (begin >> provision_port_a)
                           | (begin >> provision_port_b)
    } >> link_ports >> done
```

**Explicit `parallel()` function** (for advanced options like `retry_auth_callback`):
```python
from orchestrator.workflow import parallel

@create_workflow(...)
def create_dual_port():
    par = parallel("Provision ports",
                   begin >> provision_port_a,
                   begin >> provision_port_b,
                   retry_auth_callback=my_callback)
    return init >> par >> link_ports >> done
```

#### Dynamic parallel — one branch per item

Use when the number of branches depends on a runtime list in the workflow state (e.g., provision one port per item in `state["ports"]`).

```python
from orchestrator.workflow import foreach_parallel

@step("Fetch ports")
def fetch_ports():
    return {"ports": [{"port_id": "p1", "vlan": 100},
                      {"port_id": "p2", "vlan": 200}]}

@step("Provision port")
def provision_port(port_id, vlan):          # injected from each item
    result = call_provisioning_api(port_id, vlan)
    return {f"port_{port_id}_result": result}  # distinct key per item

@create_workflow(...)
def provision_n_ports():
    return (
        init
        >> fetch_ports
        >> foreach_parallel("Provision ports", "ports", begin >> provision_port)
        >> link_ports
        >> done
    )
```

Each item in the list becomes the seed state for one branch:

- **Dict items** are merged directly into the branch's initial state: `initial_state | {"port_id": "p1", "vlan": 100}`.
- **Scalar items** are injected as `{"item": <value>, "item_index": <int>}`.

Seed keys are injected into the branch's initial state as input-only context for that branch's steps.

#### Behavior (both kinds)

- **State isolation**: Each branch receives a deep copy of the input state. Mutations in one branch do not affect other branches.
- **Concurrent execution**: Branches execute concurrently. With ThreadPool, each branch runs in its own thread with an isolated database session (via `db.database_scope()`). With Celery, each branch runs as an independent worker task.
- **Per-branch DB logging**: Each branch writes its own `ProcessStepTable` rows, linked to the parent fork step via `ProcessStepRelationTable`. This gives fine-grained visibility into branch execution and enables the UI to render parallel branches as a tree.
- **No state merging**: Branch results are **not** merged back into the main workflow state. Each branch's final state is persisted in its own `ProcessStepTable` row, linked to the fork step via `ProcessStepRelationTable`. The main workflow continues with its pre-fork state. Branch results are accessible via the DB (and visible in the UI) but do not pollute the parent state.
- **Error propagation**: If any branch fails, the entire parallel group fails. All branches run to completion before the worst status is determined. Status priority is: Failed > Waiting > Suspend > AwaitingCallback > Success.
- **No user interaction in branches**: Parallel branches must not contain `inputstep` or `callback_step` steps. This is validated at workflow definition time.
- **Logging**: The parallel group creates a fork step in the process log. Named groups use the provided name; unnamed groups get an auto-generated name from the branch step names. Branch sub-steps appear as child rows linked via `ProcessStepRelationTable`.
- **Three or more branches**: The `|` operator chains naturally: `a | b | c` creates three parallel branches.
- **Empty list** (`foreach_parallel`): An empty `items_key` list returns `Success` with the unchanged state — no threads are created.

#### Database schema

Parallel execution introduces:

- **`ProcessStepRelationTable`**: A join table linking parent (fork) steps to child (branch) steps with `parent_step_id`, `child_step_id`, `order_id`, and `branch_index` columns.
- **Fork step columns on `ProcessStepTable`**: `parallel_total_branches` (total branch count) and `parallel_completed_count` (branches finished so far, used for atomic last-finisher detection with Celery).

#### Celery configuration

When using Celery execution, parallel branches are routed to configurable queues:

- `PARALLEL_BRANCH_QUEUE`: Queue for parallel branch tasks (default: same as regular task queue).
- `PARALLEL_BRANCH_WORKFLOW_QUEUE`: Queue for parallel branch workflow tasks (default: same as regular workflow queue).


### Execution parameters

You can fine-tune workflow execution behavior using a set of configuration parameters.
The recommended location to define or override these is in `workflows/__init__.py`.
Below are examples of key configuration options:

1. `WF_USABLE_MAP`: Define usable subscription lifecycles for workflows.

By default, the associated workflow can only be run on a subscription with a lifecycle state set to `ACTIVE`.
This behavior can be changed in the `WF_USABLE_MAP` data structure:

> note: Terminate workflows are by default, allowed to run on subscriptions in any lifecycle state unless explicitly restricted in this map.

```python
from orchestrator.services.subscriptions import WF_USABLE_MAP

WF_USABLE_MAP.update(
    {
        "validate_node_enrollment": ["active", "provisioning"],
        "provision_node_enrollment": ["active", "provisioning"],
        "modify_node_enrollment": ["provisioning"],
    }
)
```

Now validate and provision can be run on subscriptions in either `ACTIVE` or `PROVISIONING` states and modify can *only* be run on subscriptions in the `PROVISIONING` state.

2. `WF_BLOCKED_BY_IN_USE_BY_SUBSCRIPTIONS`: Block modify workflows on subscriptions with unterminated `in_use_by` subscriptions

By default, only terminate workflows are prohibited from running on subscriptions with unterminated `in_use_by` subscriptions.
This behavior can be changed in the `WF_BLOCKED_BY_IN_USE_BY_SUBSCRIPTIONS` data structure:

```python
from orchestrator.services.subscriptions import WF_BLOCKED_BY_IN_USE_BY_SUBSCRIPTIONS

WF_BLOCKED_BY_IN_USE_BY_SUBSCRIPTIONS.update(
    {
        "modify_node_enrollment": True
    }
)
```

With this configuration, both terminate and modify will not run on subscriptions with unterminated `in_use_by` subscriptions.

3. `WF_USABLE_WHILE_OUT_OF_SYNC`: Allow specific workflows on out of sync subscriptions

By default, only system workflows (tasks) are allowed to run on subscriptions that are not in sync.
This behavior can be changed with the `WF_USABLE_WHILE_OUT_OF_SYNC` data structure:

```python
from orchestrator.services.subscriptions import WF_USABLE_WHILE_OUT_OF_SYNC

WF_USABLE_WHILE_OUT_OF_SYNC.extend(
    [
        "modify_description"
    ]
)
```

Now this particular modify workflow can be run on subscriptions that are not in sync.

!!! danger
    It is potentially dangerous to run workflows on subscriptions that are not in sync. Only use this for small and
    specific usecases, such as editing a description that is only used within orchestrator.

[registering workflows]: ../../getting-started/workflows.md#register-workflows
[create_workflow]: ../../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.create_workflow
[modify_workflow]: ../../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.modify_workflow
[terminate_workflow]: ../../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.terminate_workflow
[validate_workflow]: ../../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.validate_workflow
[reconcile_workflow]: ../../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.reconcile_workflow
[functional docs for step]: ../../reference-docs/workflows/workflow-steps.md#orchestrator.workflow.step
[functional docs for retrystep]: ../../reference-docs/workflows/workflow-steps.md#orchestrator.workflow.retrystep
[functional docs for inputstep]: ../../reference-docs/workflows/workflow-steps.md#orchestrator.workflow.inputstep
[functional docs for conditional]: ../../reference-docs/workflows/workflow-steps.md#orchestrator.workflow.conditional
[functional docs for callback_step]: ../../reference-docs/workflows/callbacks.md
[Reusable step functions and singledispatch usage]: ../../reference-docs/workflows/workflow-steps.md#reusable-workflow-steps
[registering-workflows]: ../../getting-started/workflows.md#register-workflows
[tasks-and-scheduling]: ../../guides/tasks.md
