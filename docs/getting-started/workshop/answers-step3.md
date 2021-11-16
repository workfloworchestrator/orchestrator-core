# Step 3 - Answers

First generate the revision file.
```console
$ PYTHONPATH=. python main.py db revision --message "My descriptive revision description" --head=data@head
```

An example database migration.

``` python
"""My descriptive revision description.

Revision ID: 9bb25a23206b
Revises: 41e637ff569e
Create Date: 2020-12-10 21:38:39.899085

"""
from typing import Any

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
from migrations.helpers import create_missing_modify_note_workflows
from orchestrator.targets import Target

revision = "9bb25a23206b"
down_revision = "41e637ff569e"
branch_labels = None
depends_on = None


product_name = "Username registration"
workflow_name = "create_username_registration"

product_blocks: list[dict[str, Any]] = [
    {
        "name": "Username",
        "description": "Username Registration",
        "tag": "UNR",
        "status": "active",
        "resource_types": [
            ("username", "Unique name the person"),
        ],
    }
]


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO products (name, description, product_type, tag, status)"
            "VALUES (:name, :description, :product_type, :tag, :status) ON CONFLICT DO NOTHING"
        ),
        {
            "name": product_name,
            "description": "The Username product",
            "product_type": "UNPT",
            "tag": "UNR",
            "status": "active",
        },
    )
    result = conn.execute(
        sa.text("SELECT product_id FROM products WHERE name=:name"), name=product_name
    )
    product_id = result.fetchone()[0]

    for block in product_blocks:
        conn.execute(
            sa.text(
                "INSERT INTO product_blocks (name, description, tag, status) VALUES (:name, :description, :tag, :status)"
                "ON CONFLICT DO NOTHING"
            ),
            name=block["name"],
            description=block["description"],
            tag=block["tag"],
            status=block["status"],
        )
        result = conn.execute(
            sa.text("SELECT product_block_id FROM product_blocks WHERE name = :name"),
            name=block["name"],
        )
        product_block_id = result.fetchone()[0]
        conn.execute(
            sa.text(
                "INSERT INTO product_product_blocks (product_id, product_block_id) VALUES (:product_id, :product_block_id)"
                "ON CONFLICT DO NOTHING"
            ),
            product_id=product_id,
            product_block_id=product_block_id,
        )

        for resource_type, description in block["resource_types"]:
            conn.execute(
                sa.text(
                    "INSERT INTO resource_types (resource_type, description) VALUES (:resource_type, :description)"
                    "ON CONFLICT DO NOTHING"
                ),
                resource_type=resource_type,
                description=description,
            )

            result = conn.execute(
                sa.text(
                    "SELECT resource_type_id FROM resource_types where resource_type = :resource_type"
                ),
                resource_type=resource_type,
            )
            resource_type_id = result.fetchone()[0]
            conn.execute(
                sa.text(
                    "INSERT INTO product_block_resource_types (product_block_id, resource_type_id)"
                    "VALUES (:product_block_id, :resource_type_id)"
                ),
                product_block_id=product_block_id,
                resource_type_id=resource_type_id,
            )
    conn.execute(
        sa.text(
            "INSERT INTO workflows (name, target, description) VALUES (:name, :target, :description)"
            "ON CONFLICT DO NOTHING"
        ),
        {"name": workflow_name, "target": Target.CREATE, "description": "Create User"},
    )

    result = conn.execute(
        sa.text("SELECT workflow_id FROM workflows WHERE name = :name"),
        name=workflow_name,
    )
    workflow_id = result.fetchone()[0]
    result = conn.execute(
        sa.text("SELECT product_id FROM products WHERE name=:name"), name=product_name
    )
    product_id = result.fetchone()[0]
    conn.execute(
        sa.text(
            "INSERT INTO products_workflows (product_id, workflow_id) VALUES (:product_id, :workflow_id)"
            "ON CONFLICT DO NOTHING"
        ),
        {"product_id": product_id, "workflow_id": workflow_id},
    )
    create_missing_modify_note_workflows(conn)


def downgrade() -> None:

    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM products WHERE name = :name"), name=product_name)
```
