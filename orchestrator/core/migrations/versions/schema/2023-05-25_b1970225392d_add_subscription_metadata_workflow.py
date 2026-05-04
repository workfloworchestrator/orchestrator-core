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

"""Add subscription metadata workflow.

Revision ID: b1970225392d
Revises: e05bb1967eff
Create Date: 2023-05-25 09:22:46.491454

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy_utils.types.uuid import UUIDType

# revision identifiers, used by Alembic.
revision = "b1970225392d"
down_revision = "e05bb1967eff"
branch_labels = None
depends_on = None

METADATA_TABLE_NAME = "subscription_metadata"


def upgrade() -> None:
    op.create_table(
        METADATA_TABLE_NAME,
        sa.Column(
            "subscription_id",
            UUIDType(),
            nullable=False,
            index=True,
        ),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.subscription_id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {METADATA_TABLE_NAME}"))
