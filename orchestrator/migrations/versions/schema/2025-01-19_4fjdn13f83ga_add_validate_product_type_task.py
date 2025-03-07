"""Validate Product Type.

Revision ID: 4fjdn13f83ga
Revises: 2c7e8a43d4f9
Create Date: 2025-10-13 16:21:43.956814

"""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4fjdn13f83ga"
down_revision = "4c5859620539"
branch_labels = None
depends_on = None


workflow = {
    "name": "task_validate_product_type",
    "target": "SYSTEM",
    "description": "Validate all subscriptions of Product Type",
    "workflow_id": uuid4(),
}


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO workflows VALUES (:workflow_id, :name, :target, :description, now()) ON CONFLICT DO NOTHING"
        ),
        workflow,
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM workflows WHERE name = :name"), {"name": workflow["name"]})
