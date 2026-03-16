"""set is_task of task_validate_product_type to true.

Revision ID: aa1b92d0d07d
Revises: 961eddbd4c13
Create Date: 2026-03-10 14:03:36.981457

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "aa1b92d0d07d"
down_revision = "d69e10434a04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE workflows SET is_task=true WHERE name = 'task_validate_product_type'"))


def downgrade() -> None:
    pass
