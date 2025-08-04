# Creating a workflow

## Creating a Workflow

A **workflow** in Orchestrator is the combination of:

- An **initial input form** — used to collect input from the user.
- A sequence of **workflow steps** — defining the logic to be executed.

For a more detailed explanation, see  
👉 [Detailed explanation of workflows](../architecture/application/workflow.md)

---

To create a workflow, use the `@workflow` decorator. It takes the following arguments:

- `description`: A human-readable name for the workflow.
- `initial_input_form`: A function that defines the input form shown to the user.
- `target`: The workflow type — typically `Target.CREATE`, `Target.MODIFY`, or `Target.TERMINATE`.

The decorated function must return a chain of steps using the `>>` operator to define their execution order.

there are also util functions for each [workflow type](../architecture/application/workflow#subscription-workflow-types) that give usefull generic logic:

- [create_workflow](../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.create_workflow)
- [modify_workflow](../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.modify_workflow)
- [terminate_workflow](../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.terminate_workflow)
- [validate_workflow](../reference-docs/workflows/workflows.md#orchestrator.workflows.utils.validate_workflow)

For more details on these workflow types, refer to:
👉 [Subscription Workflow Types](../architecture/application/workflow.md#subscription-workflow-types)

### Minimal Example

```python
@workflow(
    "Create product subscription",
    initial_input_form=initial_input_form_generator,
    target=Target.CREATE,
)
def create_product_subscription():
    return init >> create_subscription >> done
```

In this example:

- The workflow is named **"Create product subscription"**.
- The input form is defined by `initial_input_form_generator`.
- The workflow engine will execute the steps `init`, `create_subscription`, and `done`, in that order.

Each step should be defined using the `@step` decorator and can access and update the shared subscription model.

---

### How Workflow Steps Work

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
    product: UUIDstr,
    user_input: str,
) -> State:
    subscription = build_subscription(product, user_input)
    return {"subscription": subscription}
```

In this step:

- `product` and `user_input` are populated from the `State`.
- The return value includes a new key `subscription`, which will be available to the next step in the workflow.

Every workflow starts with the builtin step `init` and ends with the builtin
step `done`, with an arbitrary list of other builtin steps or custom steps in between.

[Information about all usable step decorators can be found here](../architecture/application/workflow#workflow-steps)


## Register workflows

The orchestrator needs to know which workflows are available for which products.
This is a two stage registration process.
The workflows need to be registered as a workflow function in the code and a mapping between workflow and product_type needs to be added to the database through a migration script.
First we will add the workflow functions.
For creating the migration script, we can either let the `cli` create an empty one and fill it manually or use the `db migrate-workflows` command to generate one based on the diffs between the registered workflows in the code and the database.

### Step 1: Map workflow function to package

Registering workflow functions in the code is done by creating appropriate `LazyWorkflowInstance` instances that maps a workflow function to the Python package where it is defined.

For example, the `LazyWorkflowInstance` for the `UserGroup` create workflow looks like this:

```python
from orchestrator.workflows import LazyWorkflowInstance

LazyWorkflowInstance("workflows.user_group.create_user_group", "create_user_group")
```

Add the `LazyWorkflowInstance` calls for all six workflows to `workflows/__init__. py`, and add `import workflows` to `main.py` so the instances are created as part of the workflow package.

!!! example

    for inspiration look at an example implementation of the [lazy
    workflow instances ](https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/workflows/__init__.py)

### Step 2: Register workflow in database

There are several ways to complete this step:

- [Copy the example workflows migration](#copy-the-example-workflows-migration)
- [Migrate workflows generator script](#migrate-workflows-generator-script)
- [Manual](#manual)

#### Copy the example workflows migration

```shell
(
  cd migrations/versions/schema
  curl --remote-name https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator-beginner/main/examples/2022-11-12_8040c515d356_add_user_and_usergroup_workflows.py
)
```

And restart the Docker compose environment.

#### Migrate workflows generator script

Similar to `db migrate-domain-models`, the orchestrator command line interface offers the `db migrate-workflows` command that walks you through a menu to create a database migration file based on the difference between the registered workflows in the code and the database.

Start with the following command:

```shell
python main.py db migrate-workflows "add User and UserGroup workflows"
```

Navigate through the menu to add the six workflows to the corresponding `User` or `UserGroup` product type. After confirming a migration file will be added to `migrations/versions/schema`
The migration can be run with:

```shell
python main.py db upgrade heads
```

#### Manual

Create a new empty database migration with the following command:

```shell
PYTHONPATH=. python main.py db revision --head data --message "add User and UserGroup workflows"
```

This will create an empty database migration in the folder
`migrations/versions/schema`. For the migration we will make use of the migration helper functions `create_workflow` and `delete_workflow` that both expect a `Dict` that describes the workflow registration to be added or deleted from the database.

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


## more workflow examples for each type

### Validate

Validate workflows run integrity checks on an existing subscription. Checking the state of associated data in an external system for example. The validate migration parameters look something like this:

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

It uses a `target` of `VALIDATE`. Unlike system tasks, which use the `target` of `SYSTEM` designation, validate
workflows explicitly use `target="VALIDATE"` to distinguish themselves. This distinction reflects their different
purposes.
The `is_task` parameter is set to `True` to indicate that this workflow is a task. Tasks are workflows that are not
directly associated with a subscription and are typically used for background processing or system maintenance.
Both `SYSTEM` and `VALIDATE` workflows are considered tasks, but they serve different purposes.

Generally the steps raise assertions if a check fails, otherwise return OK to the state:

```python
@step("Check NSO")
def check_nso(subscription: NodeEnrollment, node_name: str) -> State:
    device = get_device(device_name=node_name)

    if device is None:
        raise AssertionError(f"Device not found in NSO")
    return {"check_nso": "OK"}
```

### Modify

Very similar to validate workflow but the migration params vary as one would expect with a different `target`:

```python
new_workflows = [
    {
        "name": "modify_node_enrollment",
        "target": Target.MODIFY,
        "description": "Modify Node Enrollment",
        "product_type": "Node",
        "is_task": True,
    },
]
```

It would make any desired changes to the existing subscription and if need by, change the lifecycle state at the end.
For example, for our `CREATE` that put the initial sub into the state `PROVISIONING`,
a secondary modify workflow will put it into production and then set the state to `ACTIVE` at the end:

```python
@step("Activate Subscription")
def update_subscription_and_description(subscription: NodeEnrollmentProvisioning, node_name: str) -> State:
    subscription = change_lifecycle(subscription, SubscriptionLifecycle.ACTIVE)
    subscription.description = f"Node {node_name} Production"

    return {"subscription": subscription}
```

These also have the subscription id passed in in the initial step as outlined above.

### Terminate

Terminates a workflow and undoes changes that were made.

The migration params are as one would suspect:

```python
new_workflows = [
    {
        "name": "terminate_node_enrollment",
        "target": Target.TERMINATE,
        "description": "Terminate Node Enrollment subscription",
        "product_type": "Node",
        "is_task": True,
    },
]
```

`target` is `TERMINATE`, `name` and `tag` are as you would expect.

The first step of these workflow are slightly different as it pulls in the `State` object rather than just the subscription id:

```python
@step("Load relevant subscription information")
def load_subscription_info(state: State) -> FormGenerator:
    subscription = state["subscription"]
    node = get_detailed_node(subscription["ne"]["esdb_node_id"])
    return {"subscription": subscription, "node_name": node.get("name")}
```
