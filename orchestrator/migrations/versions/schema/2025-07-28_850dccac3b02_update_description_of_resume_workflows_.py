"""Update description of resume workflows task.

Revision ID: 850dccac3b02
Revises: 93fc5834c7e5
Create Date: 2025-07-28 15:38:57.211087

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "850dccac3b02"
down_revision = "93fc5834c7e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE workflows
        SET description = 'Resume all workflows that are stuck on tasks with the status ''waiting'', ''created'' or ''resumed'''
        WHERE name = 'task_resume_workflows';
    """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE workflows
        SET description = 'Resume all workflows that are stuck on tasks with the status ''waiting'''
        WHERE name = 'task_resume_workflows';
    """
    )
