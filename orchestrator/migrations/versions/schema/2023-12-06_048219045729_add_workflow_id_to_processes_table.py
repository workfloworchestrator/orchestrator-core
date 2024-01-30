"""Add workflow_id to processes table.

Revision ID: 048219045729
Revises: da5c9f4cce1c
Create Date: 2023-12-06 15:33:46.997517

"""

import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op
from sqlalchemy.exc import IntegrityError

from orchestrator import db

# revision identifiers, used by Alembic.
revision = "048219045729"
down_revision = "da5c9f4cce1c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new processes.workflow_id column
    op.add_column("processes", column=sa.Column("workflow_id", sqlalchemy_utils.types.uuid.UUIDType()))
    # Fill workflow_id column based on the workflow name
    op.execute(
        "UPDATE processes SET workflow_id = wf.workflow_id FROM workflows wf WHERE processes.workflow = wf.name;"
    )

    try:
        op.alter_column("processes", "workflow_id", nullable=False)
    except IntegrityError:
        raise Exception(
            """
        Migration failed due to processes.workflow rows that have a workflow name that no longer exists.

        After this update, each process must be linked to a workflow.

        Follow these steps:
        1) Make a backup of the processes that are not linked to a workflow (i.e. processes.workflow does match a workflows.name).
        2) Manually delete the rows in processes that are not linked to a workflow.
        3) Re-run this migration.
        """
        )

    op.execute(
        """ALTER TABLE processes
        ADD CONSTRAINT processes_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES workflows (workflow_id);"""
    )
    op.drop_column("processes", "workflow")

    # Add deleted_at column to workflows table
    op.add_column("workflows", column=sa.Column("deleted_at", db.UtcTimestamp(timezone=True)))


def downgrade() -> None:
    op.add_column(
        "processes",
        column=sa.Column("workflow", sa.String, nullable=False, server_default=""),
    )
    op.execute(
        "UPDATE processes SET workflow = wf.name FROM workflows wf WHERE processes.workflow_id = wf.workflow_id;"
    )
    op.drop_constraint("processes_workflow_id_fkey", table_name="processes")
    op.drop_column("processes", column_name="workflow_id")
    op.drop_column("workflows", column_name="deleted_at")
