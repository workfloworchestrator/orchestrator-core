"""Deprecating workflow target in ProcessSubscriptionTable.

Revision ID: 4b58e336d1bf
Revises: 161918133bec
Create Date: 2025-07-04 15:27:23.814954

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4b58e336d1bf"
down_revision = "161918133bec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("processes_subscriptions", "workflow_target", existing_type=sa.VARCHAR(length=255), nullable=True)


def downgrade() -> None:
    op.alter_column(
        "processes_subscriptions",
        "workflow_target",
        existing_type=sa.VARCHAR(length=255),
        nullable=False,
        existing_server_default=sa.text("'CREATE'::character varying"),
    )
