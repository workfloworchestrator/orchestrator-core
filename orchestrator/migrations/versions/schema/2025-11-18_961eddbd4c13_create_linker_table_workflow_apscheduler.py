"""Create linker table workflow_apscheduler.

Revision ID: 961eddbd4c13
Revises: 850dccac3b02
Create Date: 2025-11-18 10:38:57.211087

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "961eddbd4c13"
down_revision = "850dccac3b02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE workflows_apscheduler_jobs (
            workflow_id UUID NOT NULL,
            schedule_id VARCHAR(512) NOT NULL,
            PRIMARY KEY (workflow_id, schedule_id),
            CONSTRAINT fk_workflow
                FOREIGN KEY (workflow_id)
                    REFERENCES workflows (workflow_id)
                    ON DELETE CASCADE,
            CONSTRAINT uq_workflow_schedule UNIQUE (workflow_id, schedule_id)
        );
        """
    )

    op.create_index(
        'ix_workflows_apscheduler_jobs_schedule_id',
        'workflows_apscheduler_jobs',
        ['schedule_id']
    )

def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS workflows_apscheduler_jobs;
        """
    )
