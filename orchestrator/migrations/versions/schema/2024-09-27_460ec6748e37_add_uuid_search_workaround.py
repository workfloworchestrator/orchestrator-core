"""Add uuid search workaround.

Note: this workaround was added to existing migration da5c9f4cce1c in orchestrator-core commit 3e93263.
Because of that, it was never deployed to existing environments where the original migration was already executed.

This migration (460ec6748e37) will ensure the workaround is deployed onto existing environments.
The old migration (da5c9f4cce1c) is restored to its original state before commit 3e93263.

Revision ID: 460ec6748e37
Revises: 048219045729
Create Date: 2024-09-27 18:01:14.054599

"""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "460ec6748e37"
down_revision = "048219045729"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    revision_file_path = Path(__file__)
    with open(revision_file_path.with_suffix(".sql")) as f:
        conn.execute(sa.text(f.read()))


def downgrade() -> None:
    pass
