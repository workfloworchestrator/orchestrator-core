"""Add task_validate_products.

Revision ID: 3c8b9185c221
Revises: 3323bcb934e7
Create Date: 2020-04-06 09:17:49.395612

"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3c8b9185c221"
down_revision = "3323bcb934e7"
branch_labels = None
depends_on = None

workflows = [
    {"name": "task_validate_products", "description": "Validate products", "workflow_id": uuid4(), "target": "SYSTEM"},
]


def upgrade() -> None:
    conn = op.get_bind()
    for workflow in workflows:
        conn.execute(
            sa.text(
                "INSERT INTO workflows VALUES (:workflow_id, :name, :target, :description, now()) ON CONFLICT DO NOTHING"
            ),
            **workflow,
        )


def downgrade() -> None:
    conn = op.get_bind()
    for workflow in workflows:
        conn.execute(sa.text("DELETE FROM workflows WHERE name = :name"), {"name": workflow["name"]})
