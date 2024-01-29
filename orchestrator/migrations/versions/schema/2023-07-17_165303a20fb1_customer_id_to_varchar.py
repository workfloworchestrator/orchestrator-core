"""customer_id to VARCHAR.

Revision ID: 165303a20fb1
Revises: a09ac125ea73
Create Date: 2023-07-17 13:53:23.932681

"""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "165303a20fb1"
down_revision = "a09ac125ea73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    revision_file_path = Path(__file__)
    with open(revision_file_path.with_suffix(".sql")) as f:
        conn.execute(sa.text(f.read()))


def downgrade() -> None:
    """This migration is irreversible!

    Once the type of `subscriptions.customer_id` has been changed
    from UUID to VARCHAR, it is not a failsafe operation to convert whatever value `customer_id` might now hold
    into a valid UUID type.

    In future, it will be necessary for downstream users to implement their own schema & data migrations
    if they want to (or even feasibly can) change the type of the `customer_id` column.
    """
    pass
