"""add cascade constraint on processes input state.

Revision ID: fc5c993a4b4a
Revises: 42b3d076a85b
Create Date: 2025-04-09 18:27:31.922214

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "fc5c993a4b4a"
down_revision = "42b3d076a85b"
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
