"""Add example2 product.

Revision ID: a7063f3bd74d
Revises: 3ee5ebfbaecc
Create Date: 2024-02-08 09:30:41.357761

"""

from uuid import uuid4

from alembic import op

from orchestrator.migrations.helpers import create, create_workflow, delete, delete_workflow, ensure_default_workflows
from orchestrator.targets import Target

# revision identifiers, used by Alembic.
revision = "a7063f3bd74d"
down_revision = "3ee5ebfbaecc"
branch_labels = None
depends_on = None

new_products = {
    "products": {
        "example2": {
            "product_id": uuid4(),
            "product_type": "Example2",
            "description": "Product example 2",
            "tag": "EXAMPLE2",
            "status": "active",
            "product_blocks": [
                "Example2",
            ],
            "fixed_inputs": {},
        },
    },
    "product_blocks": {
        "Example2": {
            "product_block_id": uuid4(),
            "description": "Example 2 root product block",
            "tag": "EXAMPLE2",
            "status": "active",
            "resources": {
                "example_int_enum_2": "Example 2 int enum",
            },
            "depends_on_block_relations": [],
        },
    },
    "workflows": {},
}

new_workflows = [
    {
        "name": "create_example2",
        "target": Target.CREATE,
        "description": "Create example2",
        "product_type": "Example2",
    },
    {
        "name": "modify_example2",
        "target": Target.MODIFY,
        "description": "Modify example2",
        "product_type": "Example2",
    },
    {
        "name": "terminate_example2",
        "target": Target.TERMINATE,
        "description": "Terminate example2",
        "product_type": "Example2",
    },
    {
        "name": "validate_example2",
        "target": Target.SYSTEM,
        "description": "Validate example2",
        "product_type": "Example2",
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
