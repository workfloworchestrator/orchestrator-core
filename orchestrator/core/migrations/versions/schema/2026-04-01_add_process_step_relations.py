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
"""Add process_step_relations table and parallel columns on process_steps.

Revision ID: 18a7c2676fd3
Revises: cab8b6a0ac92
Create Date: 2026-05-27 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy_utils import UUIDType

# revision identifiers, used by Alembic.
revision = "18a7c2676fd3"
down_revision = "cab8b6a0ac92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("process_steps", sa.Column("parallel_total_branches", sa.Integer(), nullable=True))
    op.add_column(
        "process_steps",
        sa.Column("parallel_completed_count", sa.Integer(), nullable=True, server_default=sa.text("0")),
    )
    op.create_table(
        "process_step_relations",
        sa.Column(
            "parent_step_id", UUIDType(), sa.ForeignKey("process_steps.stepid", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "child_step_id", UUIDType(), sa.ForeignKey("process_steps.stepid", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("order_id", sa.Integer(), primary_key=True),
        sa.Column("branch_index", sa.Integer(), nullable=False),
        sa.Column("seed_state", postgresql.JSONB(), nullable=True),
    )
    op.create_index(
        "process_step_relation_p_c_o_ix",
        "process_step_relations",
        ["parent_step_id", "child_step_id", "order_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("process_step_relation_p_c_o_ix", table_name="process_step_relations")
    op.drop_table("process_step_relations")
    op.drop_column("process_steps", "parallel_completed_count")
    op.drop_column("process_steps", "parallel_total_branches")
