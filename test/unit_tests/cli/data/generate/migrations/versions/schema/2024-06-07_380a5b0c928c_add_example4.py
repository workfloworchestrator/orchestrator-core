"""Add example4 product.

Revision ID: 380a5b0c928c
Revises: 44667c4d16cd
Create Date: 2024-06-07 10:23:26.761903

"""

from uuid import uuid4

from alembic import op
from orchestrator.migrations.helpers import create, create_workflow, delete, delete_workflow, ensure_default_workflows
from orchestrator.targets import Target

# revision identifiers, used by Alembic.
revision = "380a5b0c928c"
down_revision = "ea9e6c9de75c"
branch_labels = None
depends_on = None

new_products = {
    "products": {
        "example4": {
            "product_id": uuid4(),
            "product_type": "Example4",
            "description": "Product example 4",
            "tag": "EXAMPLE4",
            "status": "active",
            "root_product_block": "Example4",
            "fixed_inputs": {},
        },
    },
    "product_blocks": {
        "Example4Sub": {
            "product_block_id": uuid4(),
            "description": "example 4 sub product block",
            "tag": "EXAMPLE4SUB",
            "status": "active",
            "resources": {
                "str_val": "",
            },
            "depends_on_block_relations": [],
        },
        "Example4": {
            "product_block_id": uuid4(),
            "description": "Example 4 root product block",
            "tag": "EXAMPLE4",
            "status": "active",
            "resources": {
                "num_val": "",
            },
            "depends_on_block_relations": [
                "Example4Sub",
            ],
        },
    },
    "workflows": {},
}

new_workflows = [
    {
        "name": "create_example4",
        "target": Target.CREATE,
        "is_task": False,
        "description": "Create example4",
        "product_type": "Example4",
    },
    {
        "name": "modify_example4",
        "target": Target.MODIFY,
        "is_task": False,
        "description": "Modify example4",
        "product_type": "Example4",
    },
    {
        "name": "terminate_example4",
        "target": Target.TERMINATE,
        "is_task": False,
        "description": "Terminate example4",
        "product_type": "Example4",
    },
    {
        "name": "validate_example4",
        "target": Target.VALIDATE,
        "is_task": True,
        "description": "Validate example4",
        "product_type": "Example4",
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    create(conn, new_products)
    for workflow in new_workflows:
        create_workflow(conn, workflow)
    ensure_default_workflows(conn)


def downgrade() -> None:
    conn = op.get_bind()
    for workflow in new_workflows:
        delete_workflow(conn, workflow["name"])

    delete(conn, new_products)
