"""Add workflow_id to processes table.

Revision ID: 048219045729
Revises: da5c9f4cce1c
Create Date: 2023-12-06 15:33:46.997517

"""
import sqlalchemy as sa
from alembic import op
from orchestrator import db

# revision identifiers, used by Alembic.
revision = "048219045729"
down_revision = "da5c9f4cce1c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM processes WHERE NOT EXISTS (SELECT 1 FROM workflows wf WHERE processes.workflow = wf.name);"
    )
    # Set the processes.workflow column values to the corresponding workflow_id
    op.execute("UPDATE processes SET workflow = wf.workflow_id FROM workflows wf WHERE processes.workflow = wf.name;")
    # Update (column_name, column_type) to (processes.workflow_id, UUID)
    op.execute("ALTER TABLE processes RENAME COLUMN workflow TO workflow_id;")
    op.execute("ALTER TABLE processes ALTER COLUMN workflow_id TYPE uuid USING workflow_id::uuid;")
    op.execute(
        """ALTER TABLE processes 
        ADD CONSTRAINT processes_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES workflows (workflow_id);"""
    )

    # Add deleted_at column to workflows table
    op.add_column("workflows", column=sa.Column("deleted_at", db.UtcTimestamp(timezone=True)))


def downgrade() -> None:
    op.alter_column(
        "processes",
        column_name="workflow_id",
        new_column_name="workflow",
        type_=sa.String(),
    )
    op.execute("UPDATE processes SET workflow = wf.name FROM workflows wf WHERE processes.workflow = wf.workflow_id;")
    op.drop_column("processes", column_name="deleted_at")
