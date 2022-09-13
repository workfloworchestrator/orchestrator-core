"""add_minimal_impact_notification_table.

Revision ID: ea24c1e036c4
Revises: bed6bc0b197a
Create Date: 2022-09-13 13:50:58.824089

"""
import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op

from orchestrator import db

# revision identifiers, used by Alembic.
revision = "ea24c1e036c4"
down_revision = "bed6bc0b197a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "minimal_impact_notification",
        sa.Column(
            "id", sqlalchemy_utils.types.uuid.UUIDType(), server_default=sa.text("uuid_generate_v4()"), nullable=False
        ),
        sa.Column("subscription_id", sqlalchemy_utils.types.uuid.UUIDType(), nullable=False),
        sa.Column("customer_id", sqlalchemy_utils.types.uuid.UUIDType(), nullable=False),
        sa.Column(
            "impact",
            sa.Enum("Reduced Redundancy", "Loss of Resiliency", "Down time", "Never", name="impactnotificationlevel"),
            nullable=False,
        ),
        sa.Column(
            "created_at", db.UtcTimestamp(timezone=True), server_default=sa.text("current_timestamp"), nullable=False
        ),
        sa.Column(
            "last_modified", db.UtcTimestamp(timezone=True), server_default=sa.text("current_timestamp"), nullable=False
        ),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.subscription_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_id", "subscription_id", name="uniq_customer_subscription_minimal_impact_notification"
        ),
    )
    op.create_index(
        op.f("ix_minimal_impact_notification_customer_id"), "minimal_impact_notification", ["customer_id"], unique=False
    )
    op.create_index(
        op.f("ix_minimal_impact_notification_subscription_id"),
        "minimal_impact_notification",
        ["subscription_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_minimal_impact_notification_subscription_id"), table_name="minimal_impact_notification")
    op.drop_index(op.f("ix_minimal_impact_notification_customer_id"), table_name="minimal_impact_notification")
    op.drop_table("minimal_impact_notification")
