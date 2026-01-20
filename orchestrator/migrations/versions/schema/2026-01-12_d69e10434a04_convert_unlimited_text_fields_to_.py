"""Convert unlimited text fields to limited nullable strings and normalize empty subscription notes.

Revision ID: d69e10434a04
Revises: 9736496e3eba
Create Date: 2026-01-12 14:17:58.255515

"""

from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "d69e10434a04"
down_revision = "9736496e3eba"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    revision_file_path = Path(__file__.replace(".py", "_upgrade.sql"))
    with open(revision_file_path) as f:
        conn.execute(sa.text(f.read()))


def downgrade() -> None:
    conn = op.get_bind()
    revision_file_path = Path(__file__.replace(".py", "_downgrade.sql"))
    with open(revision_file_path) as f:
        conn.execute(sa.text(f.read()))

