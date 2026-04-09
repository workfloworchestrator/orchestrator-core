"""Add process_step_relations table and parallel columns on process_steps.

Revision ID: a1b2c3d4e5f6
Revises: fbc16e410bc6
Create Date: 2026-04-01 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy_utils import UUIDType

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "fbc16e410bc6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("process_steps", sa.Column("parallel_total_branches", sa.Integer(), nullable=True))
    op.add_column(
        "process_steps",
        sa.Column("parallel_completed_count", sa.Integer(), nullable=True, server_default=sa.text("0")),
    )
    op.create_table(
        "process_step_relations",
        sa.Column(
            "parent_step_id", UUIDType(), sa.ForeignKey("process_steps.stepid", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "child_step_id", UUIDType(), sa.ForeignKey("process_steps.stepid", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("order_id", sa.Integer(), primary_key=True),
        sa.Column("branch_index", sa.Integer(), nullable=False),
        sa.Column("seed_state", postgresql.JSONB(), nullable=True),
    )
    op.create_index(
        "process_step_relation_p_c_o_ix",
        "process_step_relations",
        ["parent_step_id", "child_step_id", "order_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("process_step_relation_p_c_o_ix", table_name="process_step_relations")
    op.drop_table("process_step_relations")
    op.drop_column("process_steps", "parallel_completed_count")
    op.drop_column("process_steps", "parallel_total_branches")
