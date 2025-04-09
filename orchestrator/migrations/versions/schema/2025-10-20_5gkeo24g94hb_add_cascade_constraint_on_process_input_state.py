"""Add cascade constraint on process input_state.

Revision ID: 5gkeo24g94hb
Revises: 4fjdn13f83ga
Create Date: 2025-10-20 10:15:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "5gkeo24g94hb"
down_revision = "4fjdn13f83ga"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the existing foreign key constraint
    op.drop_constraint("input_states_pid_fkey", "input_states", type_="foreignkey")

    # Add a new foreign key constraint with cascade delete
    op.create_foreign_key(
        "input_states_pid_fkey",
        "input_states",
        "processes",
        ["pid"],
        ["pid"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Drop the cascade foreign key constraint
    op.drop_constraint("input_states_pid_fkey", "input_states", type_="foreignkey")

    # Recreate the original foreign key constraint without cascade
    op.create_foreign_key(
        "input_states_pid_fkey",
        "input_states",
        "processes",
        ["pid"],
        ["pid"],
    )
