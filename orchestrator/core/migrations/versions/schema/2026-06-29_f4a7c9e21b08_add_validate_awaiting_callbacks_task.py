# Copyright 2026 SURF.
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

"""Add Validate Awaiting Callbacks task.

Revision ID: f4a7c9e21b08
Revises: cab8b6a0ac92
Create Date: 2026-06-29 09:00:00.000000

"""

from alembic import op

from orchestrator.core.migrations.helpers import create_task, delete_workflow

# revision identifiers, used by Alembic.
revision = "f4a7c9e21b08"
down_revision = "cab8b6a0ac92"
branch_labels = None
depends_on = None


task = {
    "name": "task_validate_awaiting_callbacks",
    "description": "Fail callback steps that exceeded their timeout",
}


def upgrade() -> None:
    conn = op.get_bind()
    create_task(conn, task)


def downgrade() -> None:
    conn = op.get_bind()
    delete_workflow(conn, task["name"])
