"""Make workflow description mandatory.

Revision ID: 68d14db1b8da
Revises: bac6be6f2b4f
Create Date: 2025-02-20 16:39:34.889953

"""

import sqlalchemy as sa
from alembic import op
from structlog import get_logger

logger = get_logger(__name__)

# revision identifiers, used by Alembic.
revision = "68d14db1b8da"
down_revision = "fc5c993a4b4a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
        op.alter_column("workflows", "description", existing_type=sa.TEXT(), nullable=False)
    except sa.exc.IntegrityError:
        logger.error(
            "Unable to execute migrations due to missing descriptions in workflow table, please create a migration to backfill this column."
        )
        raise


def downgrade() -> None:
    op.alter_column("workflows", "description", existing_type=sa.TEXT(), nullable=True)
