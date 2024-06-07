"""Add example1 product.

Revision ID: ea9e6c9de75c
Revises: 85be1c80731c
Create Date: 2024-02-20 21:01:56.190106

"""

from uuid import uuid4

from alembic import op
from orchestrator.migrations.helpers import create, create_workflow, delete, delete_workflow, ensure_default_workflows
from orchestrator.targets import Target

# revision identifiers, used by Alembic.
revision = "ea9e6c9de75c"
down_revision = "85be1c80731c"
branch_labels = None
depends_on = None

new_products = {
    "products": {
        "example1 1": {
            "product_id": uuid4(),
            "product_type": "Example1",
            "description": "Product example 1",
            "tag": "EXAMPLE1",
            "status": "active",
            "root_product_block": "Example1",
            "fixed_inputs": {
                "fixed_input_1": "1",
            },
        },
        "example1 10": {
            "product_id": uuid4(),
            "product_type": "Example1",
            "description": "Product example 1",
            "tag": "EXAMPLE1",
            "status": "active",
            "root_product_block": "Example1",
            "fixed_inputs": {
                "fixed_input_1": "10",
            },
        },
        "example1 100": {
            "product_id": uuid4(),
            "product_type": "Example1",
            "description": "Product example 1",
            "tag": "EXAMPLE1",
            "status": "active",
            "root_product_block": "Example1",
            "fixed_inputs": {
                "fixed_input_1": "100",
            },
        },
        "example1 1000": {
            "product_id": uuid4(),
            "product_type": "Example1",
            "description": "Product example 1",
            "tag": "EXAMPLE1",
            "status": "active",
            "root_product_block": "Example1",
            "fixed_inputs": {
                "fixed_input_1": "1000",
            },
        },
    },
    "product_blocks": {
        "Example1": {
            "product_block_id": uuid4(),
            "description": "Example 1 root product block",
            "tag": "EXAMPLE1",
            "status": "active",
            "resources": {
                "example_str_enum_1": "Example 1 str enum",
                "unmodifiable_str": "Unmodifiable resource type",
                "modifiable_boolean": "Modifiable resource type",
                "annotated_int": "Annotated integer witch min and max",
                "imported_type": "use imported type",
                "always_optional_str": "Not required in any lifecycle state",
            },
            "depends_on_block_relations": [
                "Example2",
            ],
        },
    },
    "workflows": {},
}

new_workflows = [
    {
        "name": "create_example1",
        "target": Target.CREATE,
        "description": "Create example1",
        "product_type": "Example1",
    },
    {
        "name": "modify_example1",
        "target": Target.MODIFY,
        "description": "Modify example1",
        "product_type": "Example1",
    },
    {
        "name": "terminate_example1",
        "target": Target.TERMINATE,
        "description": "Terminate example1",
        "product_type": "Example1",
    },
    {
        "name": "validate_example1",
        "target": Target.SYSTEM,
        "description": "Validate example1",
        "product_type": "Example1",
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
