"""Refactor ProcessTable.

Revision ID: 7d400516c92d
Revises: a09ac125ea73
Create Date: 2023-08-22 09:29:56.119752

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "7d400516c92d"
down_revision = "a09ac125ea73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("processes_subscriptions", "pid", nullable=False, new_column_name="process_id")
    op.alter_column("process_steps", "pid", nullable=False, new_column_name="process_id")
    op.alter_column("process_steps", "stepid", nullable=False, new_column_name="step_id")
    op.alter_column("processes", "pid", nullable=False, new_column_name="process_id")
    op.alter_column("processes", "workflow", nullable=False, new_column_name="workflow_name")


def downgrade() -> None:
    op.alter_column("processes_subscriptions", "process_id", nullable=False, new_column_name="pid")
    op.alter_column("process_steps", "process_id", nullable=False, new_column_name="pid")
    op.alter_column("process_steps", "step_id", nullable=False, new_column_name="stepid")
    op.alter_column("processes", "process_id", nullable=False, new_column_name="pid")
    op.alter_column("processes", "workflow_name", nullable=False, new_column_name="workflow")
