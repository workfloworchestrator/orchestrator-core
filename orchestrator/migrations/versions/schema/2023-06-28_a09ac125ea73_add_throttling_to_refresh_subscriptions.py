"""Add throttling to refresh_subscriptions_view trigger.

Revision ID: a09ac125ea73
Revises: b1970225392d
Create Date: 2023-06-28 15:33:36.248121

"""

from pathlib import Path

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "a09ac125ea73"
down_revision = "b1970225392d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    revision_file_path = Path(__file__)
    with open(revision_file_path.with_suffix(".sql")) as f:
        conn.execute(text(f.read()))


def downgrade() -> None:
    pass
