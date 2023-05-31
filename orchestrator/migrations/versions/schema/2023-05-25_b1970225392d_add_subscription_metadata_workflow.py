"""Add subscription metadata workflow.

Revision ID: b1970225392d
Revises: e05bb1967eff
Create Date: 2023-05-25 09:22:46.491454

"""
from uuid import uuid4

from alembic import op
import sqlalchemy

# revision identifiers, used by Alembic.
revision = "b1970225392d"
down_revision = "e05bb1967eff"
branch_labels = None
depends_on = None

workflow = {
    "name": "modify_subscription_metadata",
    "description": "Modify Subscription Metadata",
    "workflow_id": uuid4(),
    "target": "MODIFY"
}


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sqlalchemy.text(
            "INSERT INTO workflows VALUES (:workflow_id, :name, :target, :description, now()) ON CONFLICT DO NOTHING"
        ),
        **workflow,
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sqlalchemy.text("DELETE FROM workflows WHERE name = :name"), {"name": workflow["name"]})
