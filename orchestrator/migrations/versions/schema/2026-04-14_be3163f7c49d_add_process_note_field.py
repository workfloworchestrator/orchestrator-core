"""Add process note field.

Revision ID: be3163f7c49d
Revises: fbc16e410bc6
Create Date: 2026-04-14 19:56:14.971237

"""

import sqlalchemy as sa
from alembic import op

from orchestrator.db.models import StringThatAutoConvertsToNullWhenEmpty

# revision identifiers, used by Alembic.
revision = "be3163f7c49d"
down_revision = "fbc16e410bc6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("processes", sa.Column("note", StringThatAutoConvertsToNullWhenEmpty(length=5000), nullable=True))


def downgrade() -> None:
    op.drop_column("processes", "note")
