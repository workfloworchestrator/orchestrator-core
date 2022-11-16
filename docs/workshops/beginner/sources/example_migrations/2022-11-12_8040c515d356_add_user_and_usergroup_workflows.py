"""add User and UserGroup workflows.

Revision ID: 8040c515d356
Revises: 45984f4b8010
Create Date: 2022-11-12 17:05:37.434142

"""
import sqlalchemy as sa
from alembic import op
from orchestrator.migrations.helpers import create_workflow, delete_workflow
from orchestrator.targets import Target

# revision identifiers, used by Alembic.
revision = "8040c515d356"
down_revision = "45984f4b8010"
branch_labels = None
depends_on = None


new_workflows = [
    {
        "name": "create_user_group",
        "target": Target.CREATE,
        "description": "Create user group",
        "product_type": "UserGroup",
    },
    {
        "name": "modify_user_group",
        "target": Target.MODIFY,
        "description": "Modify user group",
        "product_type": "UserGroup",
    },
    {
        "name": "terminate_user_group",
        "target": Target.TERMINATE,
        "description": "Terminate user group",
        "product_type": "UserGroup",
    },
    {
        "name": "create_user",
        "target": Target.CREATE,
        "description": "Create user",
        "product_type": "User",
    },
    {
        "name": "modify_user",
        "target": Target.MODIFY,
        "description": "Modify user",
        "product_type": "User",
    },
    {
        "name": "terminate_user",
        "target": Target.TERMINATE,
        "description": "Terminate user",
        "product_type": "User",
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for workflow in new_workflows:
        create_workflow(conn, workflow)


def downgrade() -> None:
    conn = op.get_bind()
    for workflow in new_workflows:
        delete_workflow(conn, workflow["name"])
