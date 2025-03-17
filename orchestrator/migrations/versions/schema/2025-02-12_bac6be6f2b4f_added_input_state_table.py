"""Added Input State Table.

Revision ID: bac6be6f2b4f
Revises: 4fjdn13f83ga
Create Date: 2025-02-12 14:39:53.664284

"""

import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op
from sqlalchemy.dialects import postgresql

from orchestrator import db

# revision identifiers, used by Alembic.
revision = "bac6be6f2b4f"
down_revision = "4fjdn13f83ga"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "input_states",
        sa.Column(
            "input_state_id",
            sqlalchemy_utils.types.uuid.UUIDType(),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("pid", sqlalchemy_utils.types.uuid.UUIDType(), nullable=False),
        sa.Column("input_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "input_time",
            db.models.UtcTimestamp(timezone=True),
            server_default=sa.text("current_timestamp"),
            nullable=False,
        ),
        sa.Column("input_type", sa.Enum("user_input", "initial_state", name="inputtype"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pid"],
            ["processes.pid"],
        ),
        sa.PrimaryKeyConstraint("input_state_id"),
    )
    op.create_index(op.f("ix_input_state_input_state_id"), "input_states", ["input_state_id"], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_input_state_input_state_id"), table_name="input_states")
    op.drop_table("input_statse")
    # ### end Alembic commands ###
