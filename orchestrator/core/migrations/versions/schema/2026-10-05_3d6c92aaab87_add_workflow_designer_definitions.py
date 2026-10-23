# Copyright 2019-2026 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Add workflow designer definitions.

Stores what a workflow designed in the GUI runs. The workflow itself is a normal row in `workflows`.

Revision ID: 3d6c92aaab87
Revises: 544fd845554d
Create Date: 2026-10-05 14:20:55.277145
"""

import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op
from sqlalchemy.dialects import postgresql

from orchestrator.core.db.models import UtcTimestamp

# revision identifiers, used by Alembic.
revision = "3d6c92aaab87"
down_revision = "544fd845554d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_designer_definitions",
        sa.Column("workflow_id", sqlalchemy_utils.types.uuid.UUIDType(), nullable=False),
        sa.Column("definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", UtcTimestamp(timezone=True), server_default=sa.text("current_timestamp"), nullable=False
        ),
        sa.Column(
            "updated_at", UtcTimestamp(timezone=True), server_default=sa.text("current_timestamp"), nullable=False
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.workflow_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workflow_id"),
    )


def downgrade() -> None:
    # Designed workflows cannot run without their definition. Archive the ones with process history so it stays
    # readable, and remove the others.
    op.execute(
        sa.text(
            "UPDATE workflows SET deleted_at = now() WHERE deleted_at IS NULL "
            "AND workflow_id IN (SELECT workflow_id FROM workflow_designer_definitions) "
            "AND workflow_id IN (SELECT workflow_id FROM processes)"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM workflows WHERE workflow_id IN (SELECT workflow_id FROM workflow_designer_definitions) "
            "AND workflow_id NOT IN (SELECT workflow_id FROM processes)"
        )
    )
    op.drop_table("workflow_designer_definitions")
