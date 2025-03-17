"""Add subscription metadata workflow.

Revision ID: b1970225392d
Revises: e05bb1967eff
Create Date: 2023-05-25 09:22:46.491454

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy_utils.types.uuid import UUIDType

# revision identifiers, used by Alembic.
revision = "b1970225392d"
down_revision = "e05bb1967eff"
branch_labels = None
depends_on = None

METADATA_TABLE_NAME = "subscription_metadata"


def upgrade() -> None:
    op.create_table(
        METADATA_TABLE_NAME,
        sa.Column(
            "subscription_id",
            UUIDType(),
            nullable=False,
            index=True,
        ),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.subscription_id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {METADATA_TABLE_NAME}"))
