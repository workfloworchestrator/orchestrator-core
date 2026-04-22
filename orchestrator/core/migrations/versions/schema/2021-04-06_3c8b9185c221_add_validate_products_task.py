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

"""Add task_validate_products.

Revision ID: 3c8b9185c221
Revises: 3323bcb934e7
Create Date: 2020-04-06 09:17:49.395612

"""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3c8b9185c221"
down_revision = "3323bcb934e7"
branch_labels = None
depends_on = None

# NOTE: this migration forgot to insert these workflows with is_task=true. Make sure to correct that if you copy this.
workflows = [
    {"name": "task_validate_products", "description": "Validate products", "workflow_id": uuid4(), "target": "SYSTEM"},
]


def upgrade() -> None:
    conn = op.get_bind()
    for workflow in workflows:
        conn.execute(
            sa.text(
                "INSERT INTO workflows VALUES (:workflow_id, :name, :target, :description, now()) ON CONFLICT DO NOTHING"
            ),
            workflow,
        )


def downgrade() -> None:
    conn = op.get_bind()
    for workflow in workflows:
        conn.execute(sa.text("DELETE FROM workflows WHERE name = :name"), {"name": workflow["name"]})
