"""Add version column to subscription and subscription customer descriptions.

Revision ID: 4c5859620539
Revises: 460ec6748e37
Create Date: 2025-01-08 15:07:41.957937

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4c5859620539"
down_revision = "460ec6748e37"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    op.add_column(
        "subscription_customer_descriptions", sa.Column("version", sa.Integer(), server_default="1", nullable=False)
    )
    op.add_column("subscriptions", sa.Column("version", sa.Integer(), server_default="1", nullable=False))

    conn.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION increment_version()
RETURNS TRIGGER AS $$
BEGIN
    NEW.version := OLD.version + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER subscriptions_increment_version_trigger
BEFORE UPDATE ON subscriptions
FOR EACH ROW
EXECUTE FUNCTION increment_version();

CREATE TRIGGER subscription_customer_descriptions_increment_version_trigger
BEFORE UPDATE ON subscription_customer_descriptions
FOR EACH ROW
EXECUTE FUNCTION increment_version();
    """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    op.drop_column("subscriptions", "version")
    op.drop_column("subscription_customer_descriptions", "version")

    conn.execute(
        sa.text(
            """
DROP TRIGGER IF EXISTS subscriptions_increment_version_trigger on subscriptions;
DROP TRIGGER IF EXISTS subscription_customer_descriptions_increment_version_trigger on subscription_customer_descriptions;
DROP FUNCTION IF EXISTS increment_version;
"""
        )
    )
