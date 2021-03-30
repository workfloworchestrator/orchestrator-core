"""Add generic workflows to core.

Revision ID: a76b9185b334
Revises: 3323bcb934e7
Create Date: 2020-10-19 09:17:49.395612

"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a76b9185b334"
down_revision = "c112305b07d3"
branch_labels = None
depends_on = None

workflows = [
    {"name": "modify_note", "description": "Modify Note", "workflow_id": uuid4(), "target": "MODIFY"},
    {"name": "task_clean_up_tasks", "description": "Clean up old tasks", "workflow_id": uuid4(), "target": "SYSTEM"},
    {
        "name": "task_resume_workflows",
        "description": "Resume all workflows that are stuck on tasks with the status 'waiting'",
        "workflow_id": uuid4(),
        "target": "SYSTEM",
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for workflow in workflows:
        conn.execute(
            sa.text(
                "INSERT INTO workflows VALUES (:workflow_id, :name, :target, :description, now()) ON CONFLICT DO NOTHING"
            ),
            **workflow,
        )


def downgrade() -> None:
    conn = op.get_bind()
    for workflow in workflows:
        conn.execute(sa.text("DELETE FROM workflows WHERE name = :name"), {"name": workflow["name"]})
