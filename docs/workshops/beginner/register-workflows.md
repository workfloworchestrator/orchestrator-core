# Register workflows

The orchestrator needs to know which workflows are available for which
products.  This is a two stage registration process. First a new database
migration is made to add a mapping between workflow function and a product.

Create a new empty database migratrion with the following command:

```shell
PYTHONPATH=. python main.py db revision --head data --message "add User and UserGroup workflows"
```

This will create an empty database migration in the folder
`migrations/versions/schema`. For the migration we will make use of the
migration helper functions `create_workflow` and `delete_workflow` that both
expect a `Dict` that describes the workflow registration to be added or deleted
from the database.

To add all User and UserGroup workflows in bulk a list of `Dict` is created,
for only the UserGroup create workflow the list looks like this:

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

This registers the workflow function `create_user_group` as a create workflow
for the `UserGroup` product.

Add the import as shown above and a list of the create, modify and terminate workflows for both the
`UserGroup` and `User` products to the migration that was created above.

The migration `upgrade` and `downgrade` functions will just loop through the
list:

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

Add the import and code as shown above to the migration and run the migration with the following command:

```shell
PYTHONPATH=. python main.py db upgrade heads
```

!!! example

    for inspiration, have a look at this example 
    [Add User and UserGroup workflows
    ](https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/example_migrations/2022-11-12_8040c515d356_add_user_and_usergroup_workflows.py)
    migration


The second stage of the registration process consists of telling the
orchestrator where to find the workflow functions that are registered in the
database. This is done by creating the appropriate `LazyWorkflowInstance`
instance that maps a workflow function to the Python package where it is
defined.

For example, the `LazyWorkflowInstance` for the `UserGroup` create workflow
looks like this:

```python
from orchestrator.workflows import LazyWorkflowInstance

LazyWorkflowInstance("workflows.user_group.create_user_group", "create_user_group")
```

Add all `LazyWorkflowInstance` for all six workflows to `workflows/__init__.
py`, and add the following import statement to`main.py` so the instances are
created as part of the workflow package initialization:

```python
import workflows
```

!!! example

    for inspiration look at an example implementation of the [lazy
    workflow instances ](https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/workflows/__init__.py)
