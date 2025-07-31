# What is a workflow and how does it work?
The workflow engine is the core of the software, it has been created to execute a number of functions.

- Safely and reliable manipulate customer `Subscriptions` from one state to the next and maintain auditability.
- Create an API through which programmatically `Subscriptions` can be manipulated.
- Execute step functions in order and allow the retry of previously failed process-steps in an idempotent way.
- Atomically execute workflow functions.

### Best Practices
The orchestrator will always attempt to be a robust a possible when executing workflow steps. However it is always
up to the developer to implement the best practices as well as he/she can.

#### Safeguards in the orchestrator;
* Steps will be treated as atomic units: All code must execute otherwise the state will not be commited to the
  database. For this reason it is not possible to call `.commit()` on the ORM within a step function
* Workflows are only allowed to be run on `insync` subscriptions, unless explicitly configured otherwise. This is to
  safeguard against resource contention. One of the first things a workflow should do is set the subscription it it
  manipulating `out of sync`. No other workflow can then manipulate it.
* Failed steps can be retried again and again, they use the state from the **last successful** step as their
  starting point.

#### Coding gotchas
* The orchestrator is best suited to be used as a data manipulator, not as a data transporter. Use the State log as
  a log of work, not a log of data. If the data you enter in the state is corrupt or wrong, you might need to
  attempt a very difficult database query to update the state to solve your conflict
* Always fetch data needed from an external system, **Just in time**. This will increase the robustness of the step
* Always create a step function that executes one piece of work at a time. Theoretically you can execute the whole
  workflow in a single  step. However this does not help with traceability and reliability.


## Workflows

> [explanation to create workflow in code](../../getting-started/workflows.md)

Workflows are composed of one or more **steps**, each representing a discrete unit of work in the subscription management process. Steps are executed sequentially by the workflow engine and are the fundamental building blocks of workflows.

There are two high-level kinds of workflows:

- workflows
    - Defined for specific products.
    - Perform operations like creating, modifying, or terminating subscriptions.
- tasks
    - Not tied to a specific product and may not involve a subscription at all.
    - Can be scheduled to run periodically or triggered manually.
    - Useful for actions like cleanup jobs or triggering validations across multiple subscriptions.
    - Examples can be found in `orchestrator.workflows.tasks`.

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

A Default Workflows mechanism is provided to provide a way for a given workflow to be automatically attached to all Products. To ensure this, modify the `DEFAULT_PRODUCT_WORKFLOWS` environment variable, and be sure to use `helpers.create()` in your migration.

Alternatively, be sure to execute `ensure_default_workflows()` within the migration if using `helpers.create()` is not desirable.

By default, `DEFAULT_PRODUCT_WORKFLOWS` is set to `['modify_note']`.


## Workflow Steps

Workflows are composed of one or more **steps**, where each step is executed sequentially by the workflow engine and are the fundamental building blocks of workflows.

### Step Characteristics

- **Atomicity**: Each step is atomic-either it fully completes or has no effect. This ensures data consistency and reliable state transitions.
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


## OLD

## Creating a Workflow

The "base" workflow for a product is the `Create` workflow. This defines how a subscription is initially created, and all other workflows (e.g., modify, terminate, validate) are associated with it.

To create a workflow, follow these steps:

The "base" workflow out of a set is the `CREATE` workflow. That will create a subscription and all of the associated workflows "nest" under that. to create a workflow, there are 2 steps, creating the function and registering it using `LazyWorkflowInstance` and the other is adding the workflow to the database.

### registering a workflow

to register a workflow created in the code, we need to create a database migration and initialize

We need to create a workflow migration to add the workflow to the database.
The migration needs to define a specific set of parameters:

```python
params_create = dict(
    name="create_node_enrollment",
    target="CREATE",
    description="Create Node Enrollment Service",
    tag="NodeEnrollment",
    search_phrase="Node Enrollment%",
)
```

The `name` is the actual name of the workflow as defined in the workflow code itself:

```python
from orchestrator.workflows.utils import create_workflow

@create_workflow(
    "Create Node Enrollment",
    initial_input_form=initial_input_form_generator,
    status=SubscriptionLifecycle.PROVISIONING
)
def create_node_enrollment() -> StepList:
    return (
        begin
        >> construct_node_enrollment_model
        >> store_process_subscription()
        ...
```

The `target` is `CREATE`, `description` is a human readable label and the `tag` is a specific string that will be used in all of the associated workflows.

### Create flow

Generally the initial step will be the form generator function to display information and gather user input. The first actual step (`construct_node_enrollment_model` here) is generally one that takes data gathered in the form input step (and any data gathered from external systems, etc) and constructs the populated domain model.

Note that at this point the subscription is created with a lifecycle state of `INITIAL`.

The domain model is then returned as part of the `subscription` object along with any other data downstream steps might want:

```python
@step("Construct Node Enrollment model")
def construct_node_enrollment_model(
    product: UUIDstr, customer_id: UUIDstr, esdb_node_id: int, select_node: str, url: str, uuid: str, role_id: str
) -> State:
    subscription = NodeEnrollmentInactive.from_product_id(
        product_id=product, customer_id=customer_id, status=SubscriptionLifecycle.INITIAL
    )

    subscription.ne.esdb_node_id = esdb_node_id
    subscription.description = f"Node {select_node} Initial Subscription"
    subscription.ne.esdb_node_uuid = uuid
    subscription.ne.nso_service_id = uuid4()
    subscription.ne.routing_domain = "esnet-293"

    role = map_role(role_id, select_node)
    site_id = select_node.split("-")[0] # location short name

    return {
        "subscription": subscription,
        "subscription_id": subscription.subscription_id,
        "subscription_description": subscription.description,
        "role": role,
        "site_id": site_id
    }
```

After that the the subscription is created and registered with the orchestrator:

```python
    >> store_process_subscription()
```

The subsequent steps are the actual logic being executed by the workflow. It's a best practice to have each step execute one discrete operation so in case a step fails it can be restarted. To wit if a step contained:

```python
@step("Do things rather than thing")
def do_things(subscription: NodeEnrollmentProvisioning):

    do_x()

    do_y()

    do_z()

    return {"subscription": subscription}
```

And `do_z()` fails, restarting the workflow will execute the first two steps again and that might cause problems.

The final step will make any final changes to the subscription information and change the state of the subscription to (usually) `PROVISIONING` or `ACTIVE`:

```python
@step("Update subscription name with node info")
def update_subscription_name_and_description(subscription: NodeEnrollmentProvisioning, select_node: str) -> State:
    subscription = change_lifecycle(subscription, SubscriptionLifecycle.PROVISIONING)
    subscription.description = f"Node {select_node} Provisioned (without system service)"

    return {"subscription": subscription}
```

No other magic really, when this step completes successfully the workflow is done and the active subscription will show up in the orchestrator UI.

## Associated workflows

Now with an active subscription, the associated workflows (modify, validate, terminate, etc) "nest" under the active subscription in the UI. When they are executed they are run "on" the subscription they are associated with.

Like the `CREATE` workflow they *can* have an initial form generator step but they don't necessarily need one. For example a validate workflow probably would not need any additional input since it's just running checks on an existing subscription.

These workflows have more in common with each other than not, it's mostly a matter of how they are registered with the system.

### Execution parameters

There are a few parameters to finetune workflow execution constraints. The recommended place to alter them is from the workflows module, i.e. in `workflows/__init__.py`. Refer to the examples below.

1. `WF_USABLE_MAP`: configure subscription lifecycles on which a workflow is usable

By default, the associated workflow can only be run on a subscription with a lifecycle state set to `ACTIVE`. This behavior can be changed in the `WF_USABLE_MAP` data structure:

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

Now validate and provision can be run on subscriptions in either `ACTIVE` or `PROVISIONING` states and modify can *only* be run on subscriptions in the `PROVISIONING` state. The exception is terminate, those workflows can be run on subscriptions in any state unless constrained here.

2. `WF_BLOCKED_BY_IN_USE_BY_SUBSCRIPTIONS`: block modify workflows on subscriptions with unterminated `in_use_by` subscriptions

By default, only terminate workflows are prohibited from running on subscriptions with unterminated `in_use_by` subscriptions. This behavior can be changed in the `WF_BLOCKED_BY_IN_USE_BY_SUBSCRIPTIONS` data structure:

```python
from orchestrator.services.subscriptions import WF_BLOCKED_BY_IN_USE_BY_SUBSCRIPTIONS

WF_BLOCKED_BY_IN_USE_BY_SUBSCRIPTIONS.update(
    {
        "modify_node_enrollment": True
    }
)
```

With this configuration, both terminate and modify will not run on subscriptions with unterminated `in_use_by` subscriptions.

3. `WF_USABLE_WHILE_OUT_OF_SYNC`: allow specific workflows on out of sync subscriptions

By default, only system workflows (tasks) are allowed to run on subscriptions that are not in sync. This behavior can be changed with the `WF_USABLE_WHILE_OUT_OF_SYNC` data structure:

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
