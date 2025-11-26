"""Create linker table workflow_apscheduler.

Revision ID: 961eddbd4c13
Revises: 850dccac3b02
Create Date: 2025-11-18 10:38:57.211087

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "961eddbd4c13"
down_revision = "850dccac3b02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if the apscheduler_jobs table exists and create it if it does not exist.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "apscheduler_jobs" not in inspector.get_table_names():
        op.execute(
            sa.text(
                """
            CREATE TABLE apscheduler_jobs
            (
                id            VARCHAR(191) NOT NULL PRIMARY KEY,
                next_run_time DOUBLE PRECISION,
                job_state     bytea NOT NULL
            );
            """
            )
        )

    # Notice the VARCHAR(512) for schedule_id to accommodate longer IDs
    # This so that if APScheduler changes its ID format in the future, we are covered.
    op.execute(
        sa.text(
            """
            CREATE TABLE workflows_apscheduler_jobs (
                workflow_id UUID NOT NULL,
                schedule_id VARCHAR(512) NOT NULL,
                PRIMARY KEY (workflow_id, schedule_id),
                CONSTRAINT fk_workflow
                    FOREIGN KEY (workflow_id) REFERENCES public.workflows (workflow_id)
                        ON DELETE CASCADE,
                CONSTRAINT fk_schedule
                    FOREIGN KEY (schedule_id) REFERENCES public.apscheduler_jobs (id)
                        ON DELETE CASCADE,
                CONSTRAINT uq_workflow_schedule UNIQUE (workflow_id, schedule_id)
            );
            """
        )
    )

    op.create_index("ix_workflows_apscheduler_jobs_schedule_id", "workflows_apscheduler_jobs", ["schedule_id"])


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DROP TABLE IF EXISTS workflows_apscheduler_jobs;
            """
        )
    )
