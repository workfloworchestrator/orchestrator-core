# Workflows

## Creating a workflow

A **workflow** is the combination of:

- An **initial input form** — used to collect input from the user.
- A sequence of **workflow steps** — defining the logic to be executed.

For a more detailed explanation, see  
👉 [Detailed explanation of workflows](../architecture/application/workflow.md)

---

There are specialized decorators for each [workflow type] that execute "default" steps before and after the steps from your workflow.
It is recommended to use these decorators because they ensure correct functioning of the Orchestrator.

- [create_workflow]
- [modify_workflow]
- [terminate_workflow]
- [validate_workflow]

under the hood they all use a [workflow] decorator which can be used for tasks that don't fit any of the types above.

The decorated function must return a chain of steps using the `>>` operator to define their execution order.

### Minimal create workflow example

```python
from orchestrator.workflows.utils import create_workflow
from orchestrator.workflow import StepList, begin


@create_workflow(
    "Create product subscription",
    initial_input_form=initial_input_form_generator
)
def create_product_subscription() -> StepList:
    return begin >> create_subscription
```

In this example:

- The workflow is named **"Create product subscription"**.
- The input form is defined by `initial_input_form_generator`.
- The workflow engine will execute the steps inside `create_workflow` before returned steps,
   `create_subscription`, and steps inside `create_workflow` after returned steps.

Each step should be defined using the `@step` decorator and can access and update the shared subscription model.

---

### How workflow steps work

Information between workflow steps is passed using `State`, which is nothing more than a collection of key/value pairs.
In Python the state is represented by a `Dict`, with string keys and arbitrary values.
Between steps the `State` is serialized to JSON and stored in the database.

The `@step` decorator converts a function into a workflow step.
Arguments to the step function are automatically filled using matching keys from the `State`.
The function must return a dictionary of new or updated key-value pairs, which are merged into the `State` and passed to the next step.
The serialization and deserialization between JSON and the indicated Python types are done automatically.
A minimal workflow step looks as follows:

```python

@step("Create subscription")
def create_subscription(
    product: UUID,
    user_input: str,
) -> State:
    subscription = build_subscription(product, user_input)
    return {"subscription": subscription}
```

In this step:

- `product` and `user_input` are populated from the `State`.
- The return value includes a new key `subscription`, which will be available to the next step in the workflow.

Every workflow starts with the builtin step `init` and ends with the builtin step `done`,
 with an arbitrary list of other builtin steps or custom steps in between.  
the [workflow type] decorators have these included and can use `begin >> your_step`.

Domain models as parameters are subject to special processing.
With the previous step, the `subscription` is available in the state, which for the next step, can be used directly with the Subscription model type, for example:

```python
@step("Add subscription to external system")
def add_subscription_to_external_system(
    subscription: MySubscriptionModel,
) -> State:
    payload = subscription.my_block
    response = add_to_external_system(payload)
    return {"response": response}
```

For `@modify_workflow`, `@validate_workflow` and `@terminate_workflow` the `subscription` is directly usable from the first step.

[Information about all usable step decorators can be found here](../architecture/application/workflow#workflow-steps)

## Register workflows

To make workflows available in the orchestrator, they must be registered in two stages:

1. In code — by defining them as workflow functions and registering them via `LazyWorkflowInstance`.
2. In the database — by mapping them to the corresponding `product_type` using a migration.
    - workflows don't need to necessarily be added to a product_type, doing this will only make them available as tasks not meant to be ran by a subscription.

We’ll start with the code registration, followed by options for generating the database migration.

### Step 1: Register workflow functions in code

Workflow functions must be registered by creating a `LazyWorkflowInstance`, which maps a workflow function to the Python module where it's defined.

Example — registering the `create_user_group` workflow:

```python
from orchestrator.workflows import LazyWorkflowInstance

LazyWorkflowInstance("workflows.user_group.create_user_group", "create_user_group")
```

To ensure the workflows are discovered at runtime:

- Add all `LazyWorkflowInstance(...)` calls to `workflows/__init__.py`.
- Add `import workflows` to `main.py` so they are registered during app startup.

!!! example

    for inspiration look at an example implementation of the [lazy workflow instances]

### Step 2: Register workflows in the database

After registering workflows in code, you need to add them to the database by mapping them to their `product_type`.
There are three ways to do this:

- [Migrate workflows generator script](#migrate-workflows-generator-script)
- [Copy the example workflows migration](#copy-the-example-workflows-migration)
- [Manual](#manual)

#### Migrate workflows generator script

Similar to `db migrate-domain-models`, the orchestrator command line interface offers the `db migrate-workflows` command
that walks you through a menu to create a database migration file based on the difference between the registered workflows in the code and the database.

Start with the following command:

```shell
python main.py db migrate-workflows "add User and UserGroup workflows"
```

Navigate through the menu to add the six workflows to the corresponding `User` or `UserGroup` product type.
After confirming a migration file will be added to `migrations/versions/schema`.

The migration can be run with:

```shell
python main.py db upgrade heads
```

#### Copy the example workflows migration

You can copy a predefined migration file from the example repository:

```shell
(
  cd migrations/versions/schema
  curl --remote-name https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator-beginner/main/examples/2022-11-12_8040c515d356_add_user_and_usergroup_workflows.py
)
```

Update it to your own workflow and update the database with:

```shell
python main.py db upgrade heads
```

#### Manual

Create a new empty database migration with the following command:

```shell
PYTHONPATH=. python main.py db revision --head data --message "add User and UserGroup workflows"
```

This will create an empty database migration in the folder `migrations/versions/schema`.
For the migration we will make use of the migration helper functions `create_workflow` and `delete_workflow` that both expect a `Dict` that describes the workflow registration to be added or deleted from the database.

To add all User and UserGroup workflows in bulk a list of `Dict` is created, for only the UserGroup create workflow the list looks like this:

```python
from orchestrator.targets import Target

new_workflows = [
    {
        "name": "create_user_group",
        "target": Target.CREATE,
        "description": "Create user group",
        "product_type": "UserGroup",
    },
]
```

This registers the workflow function `create_user_group` as a create workflow for the `UserGroup` product.

Add a list of `Dict`s describing the create, modify and terminate workflows for both the `UserGroup` and `User` products to the migration that was created above.

The migration `upgrade` and `downgrade` functions will just loop through the list:

```python
from orchestrator.migrations.helpers import create_workflow, delete_workflow


def upgrade() -> None:
    conn = op.get_bind()
    for workflow in new_workflows:
        create_workflow(conn, workflow)


def downgrade() -> None:
    conn = op.get_bind()
    for workflow in new_workflows:
        delete_workflow(conn, workflow["name"])
```

Run the migration with the following command:

```shell
PYTHONPATH=. python main.py db upgrade heads
```


## More workflow examples

### Validate

Validate workflows run integrity checks on an existing subscription.
Checking the state of associated data in an external system for example.
The validate migration parameters look something like this:

```python
new_workflows = [
    {
        "name": "validate_node_enrollment",
        "target": Target.VALIDATE,
        "description": "Validate Node Enrollment before production",
        "product_type": "Node",
        "is_task": True,
    },
]
```

This workflow uses `Target.VALIDATE`, which explicitly distinguishes it from system tasks that use `Target.SYSTEM`.
While both are marked with `is_task=True` and treated as tasks, they serve different purposes:

- `SYSTEM` workflows are typically used for background processing and internal orchestration.
- `VALIDATE` workflows are used to confirm that a subscription is still correct and consistent, verifying that external systems are still in sync with it.

Validate workflow steps generally raise an `AssertionError` when a condition fails.
If all checks pass, they return a simple success marker (e.g., "OK") to the workflow state.


```python
@step("Check NSO")
def check_nso(subscription: NodeEnrollment, node_name: str) -> State:
    device = get_device(device_name=node_name)

    if device is None:
        raise AssertionError(f"Device not found in NSO")
    return {"check_nso": "OK"}
```

### Modify

The `Modify` workflow is similar to a `Validate` workflow, but uses different migration parameters appropriate to its `Target.MODIFY` context.

```python
new_workflows = [
    {
        "name": "modify_node_enrollment",
        "target": Target.MODIFY,
        "description": "Modify Node Enrollment",
        "product_type": "Node",
    },
]
```

This type of workflow applies changes to an existing subscription.
If necessary, it can also update the subscription’s lifecycle state at the end of the process.
For example, suppose a `CREATE` workflow initially sets the subscription to the `PROVISIONING` state.
A follow-up `Modify` workflow might transition it to production and set the lifecycle state to `ACTIVE`:

```python
@step("Activate Subscription")
def update_subscription_and_description(subscription: NodeEnrollmentProvisioning, node_name: str) -> State:
    subscription = NodeEnrollment.from_other_lifecycle(subscription)
    subscription.description = f"Node {node_name} Production"

    return {"subscription": subscription}
```

These also have the `subscription` passed in in the initial step as outlined above.

### Terminate

A Terminate workflow is used to cleanly remove a subscription and undo any changes made during its lifecycle.

The migration params are as one would suspect:

```python
new_workflows = [
    {
        "name": "terminate_node_enrollment",
        "target": Target.TERMINATE,
        "description": "Terminate Node Enrollment subscription",
        "product_type": "Node",
    },
]
```
Here, the `target`, `name`, and `description` follow standard naming conventions for `terminate` workflows.

The first step of a terminate workflow can be used to store identifiers in the state, for example:

```python
@step("Load relevant subscription information")
def load_subscription_info(subscription: NodeEnrollment) -> FormGenerator:
    node = get_detailed_node(subscription.ne.esdb_node_id)
    return {"subscription": subscription, "node_name": node.get("name")}
```

This approach ensures that the workflow has all the necessary context to safely tear down the subscription and associated resources.

[create_workflow]: ../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.create_workflow
[modify_workflow]: ../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.modify_workflow
[terminate_workflow]: ../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.terminate_workflow
[validate_workflow]: ../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.validate_workflow
[workflow]: ../reference-docs/workflows/workflows.md#orchestrator.workflow.workflow
[workflow type]: ../architecture/application/workflow#subscription-workflow-types
[lazy workflow instances]: https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/workflows/__init__.py
