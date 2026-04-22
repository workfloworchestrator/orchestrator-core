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

"""Deprecating workflow target in ProcessSubscriptionTable.

Revision ID: 4b58e336d1bf
Revises: 161918133bec
Create Date: 2025-07-04 15:27:23.814954

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4b58e336d1bf"
down_revision = "161918133bec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("processes_subscriptions", "workflow_target", existing_type=sa.VARCHAR(length=255), nullable=True)


def downgrade() -> None:
    op.alter_column(
        "processes_subscriptions",
        "workflow_target",
        existing_type=sa.VARCHAR(length=255),
        nullable=False,
        existing_server_default=sa.text("'CREATE'::character varying"),
    )
