"""simple service port.

Revision ID: b704a62833fb
Revises: 30469277166f
Create Date: 2022-02-13 10:34:09.670119

"""
from typing import Any

import sqlalchemy as sa
from alembic import op
from orchestrator.targets import Target

from migrations.helpers import create_missing_modify_note_workflows

# revision identifiers, used by Alembic.
revision = 'b704a62833fb'
down_revision = None
branch_labels = ("data",)
depends_on = "3323bcb934e7"

workflow_name = "create_sp"

product: dict[str, Any] = {
    "name": "service-port",
    "description": "Service Port",
    "product_type": "Port",
    "tag": "SP",
    "status": "active",
}

product_blocks: list[dict[str, Any]] = [
    {
        "name": "service-port",
        "description": "Service Port",
        "tag": "Port",
        "status": "active",
        "resource_types": [
            ("port_mode", "Port Mode (untagged, tagged)."),
            ("port_id", "Port ID from Inventory Management System)."),
            # ID in Inventory Management System
            # ID in Network Management System
        ],
    },
]

fixed_inputs: dict[str, Any] = {
    "port_speed": [1000],
}


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO products (name, description, product_type, tag, status)"
            "VALUES (:name, :description, :product_type, :tag, :status) ON CONFLICT DO NOTHING"
        ),
        product,
    )
    result = conn.execute(
        sa.text("SELECT product_id FROM products WHERE name=:name"),
        name=product["name"],
    )
    product_id = result.fetchone()[0]
    print(product_id)

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
                    "VALUES (:product_block_id, :resource_type_id) ON CONFLICT DO NOTHING"
                ),
                product_block_id=product_block_id,
                resource_type_id=resource_type_id,
            )
    for fi_name in fixed_inputs:
        for fi_value in fixed_inputs[fi_name]:
            conn.execute(
                sa.text(
                    "INSERT INTO fixed_inputs (name, value, product_id) VALUES (:name, :value, :product_id)"
                    "ON CONFLICT DO NOTHING"
                ),
                name=fi_name,
                value=fi_value,
                product_id=product_id,
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
        sa.text("SELECT product_id FROM products WHERE name=:name"),
        name=product["name"],
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
    conn.execute(
        sa.text("DELETE FROM products WHERE name = :name"), name=product["name"]
    )