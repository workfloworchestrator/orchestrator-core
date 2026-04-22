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
