# What is a workflow and how does it work?
The workflow engine is the core of the software, it has been created to execute a number of functions.

- Safely and reliable manipulate customer `Subscriptions` from one state to the next and maintain auditability.
- Create an API through which programmatically `Subscriptions` can be manipulated.
- Execute step functions in order and allow the retry of previously failed process-steps in an idempotent way.
- Atomically execute workflow functions.

### Best Practices
The orchestrator will always attempt to be as robust as possible when executing workflow steps.
However it is always up to the developer to implement the best practices as well as he/she can.

#### Safeguards in the orchestrator;
- **Atomic Step Execution**: Each step is treated as an atomic unit.
  If a step fails, no partial changes are committed to the database.
  Because of this, calling .commit() on the ORM within a step function is not allowed.
- **`insync` Subscription Requirement**: By default, workflows can only run on subscriptions that are marked as `insync`, unless explicitly configured otherwise.
  This prevents multiple workflows from manipulating the same subscription concurrently.
  One of the first actions a workflow should perform is to mark the subscription as `out of sync` to avoid conflicts.
- **Step Retry Behavior**: Failed steps can be retried indefinitely. Each retry starts from the state of the **last successfully completed** step.


#### Coding gotchas
- The orchestrator is best suited to be used as a data manipulator, not as a data transporter.
  - Use the State log as a log of work, not a log of data.
  - If the data you enter in the state is corrupt or wrong, you might need to attempt a very difficult database query to update the state to solve your conflict.
- Always retrieve external data at the moment it's needed during a step. This increases the robustness of the step.
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

workflows need to be registered in the database and initialized as a `LazyWorkflowInstance` to work, [more info on this here](../../getting-started/workflows.md#register-workflows)

### Subscription Workflow Types

Workflows are categorized based on the operations they perform on a subscription:

- Create ([create_workflow](../../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.create_workflow))
    - The "base" workflow that initializes a new subscription for the product.
    - Only one create workflow should exist per product.
- Modify ([modify_workflow](../../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.modify_workflow))
    - Modify an existing subscription (e.g., updating parameters, migrating to another product).
    - Multiple modify workflows can exist, each handling a specific type of modification.
- Terminate ([terminate_workflow](../../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.terminate_workflow))
    - Terminates the subscription and removes its data and references from external systems.
    - External references should only be retained if they also hold historical records.
    - Only one terminate workflow should exist per product.
- Validate ([validate_workflow](../../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.validate_workflow))
    - Verifies that external systems are consistent with the orchestrator's subscription state.
    - Only one validate workflow should exist per product.


### Default Workflows

A Default Workflows mechanism is provided to provide a way for a given workflow to be automatically attached to all Products.
To ensure this, modify the `DEFAULT_PRODUCT_WORKFLOWS` environment variable, and be sure to use `helpers.create()` in your migration.

Alternatively, be sure to execute `ensure_default_workflows()` within the migration if using `helpers.create()` is not desirable.

By default, `DEFAULT_PRODUCT_WORKFLOWS` is set to `['modify_note']`.


## Workflow Steps

Workflows are composed of one or more **steps**, where each step is executed sequentially by the workflow engine and are the fundamental building blocks of workflows.

### Step Characteristics

- **Atomicity**: Each step is atomic, either it fully completes or has no effect. This ensures data consistency and reliable state transitions.
- **Idempotency**: Steps should be designed to be safely repeatable without causing unintended side effects.
- **Traceability**: By breaking workflows into fine-grained steps, the orchestrator maintains clear audit trails and simplifies error handling and retries.

### Types of Steps

The orchestrator supports several kinds of steps to cover different use cases:

- **`step`** [functional docs here](../../reference-docs/workflows/workflow-steps.md#orchestrator.workflow.step)  
  Executes specific business logic or external API calls as part of the subscription process.

- **`retrystep`** [functional docs here](../../reference-docs/workflows/workflow-steps.md#orchestrator.workflow.retrystep)  
  Similar to `step`, but designed for operations that may fail intermittently. These steps will automatically be retried periodically on failure.

- **`inputstep`** [functional docs here](../../reference-docs/workflows/workflow-steps.md#orchestrator.workflow.inputstep)  
  Pauses the workflow to request and receive user input during execution.

- **`conditional`** [functional docs here](../../reference-docs/workflows/workflow-steps.md#orchestrator.workflow.conditional)  
  Conditionally executes the step based on environment variables or process state.  
  If the condition evaluates to false, the step is skipped entirely.

- **`callback_step`** [functional docs here](../../reference-docs/workflows/callbacks.md)  
  Pauses workflow execution while waiting for a external event to complete.

For a practical example of how to define reusable workflow steps—and how to leverage singledispatch for type-specific logic—see:
👉 [Reusable step functions and singledispatch usage](../../reference-docs/workflows/workflow-steps.md#reusable-workflow-steps-in-orchestrator-core)


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
