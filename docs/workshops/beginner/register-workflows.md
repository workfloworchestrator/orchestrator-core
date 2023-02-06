# Register workflows

The orchestrator needs to know which workflows are available for which products. This is a two stage registration process. The workflows need to be registered as a workflow function in the code and a mapping between workflow and product_type needs to be added to the database through migration
script. First we will add the workflow functions. For creating the migration script, we can either let the `cli` create an empty one and fill it manually or use the `db migrate-workflows` command to generate one based on the diffs between the registered workflows in the code and the database.

## Step 1: Map workflow function to package

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

## Step 2: Register workflow in database

There are several ways to complete this step:

- [Copy the example workflows migration file from the example repository](#copy-the-example-workflows-migration)
- [Use the `db migrate-workflows` generator script](#migrate-workflows-generator-script)
- [Create an empty migration file and edit it](#manual)

### Copy the example workflows migration

```shell
(
  cd migrations/versions/schema
  curl --remote-name https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator-beginner/main/examples/2022-11-12_8040c515d356_add_user_and_usergroup_workflows.py
)
```

And restart the Docker compose environment.

### Migrate workflows generator script

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

### Manual

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
