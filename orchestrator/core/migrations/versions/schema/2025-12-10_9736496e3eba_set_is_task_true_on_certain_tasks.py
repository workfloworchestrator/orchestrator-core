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

"""Set is_task=true on certain tasks.

This is required to make them appear in the completed tasks in the UI, and for the cleanup task to be able to
remove them.

Revision ID: 9736496e3eba
Revises: 961eddbd4c13
Create Date: 2025-12-10 16:42:29.060382

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9736496e3eba"
down_revision = "961eddbd4c13"
branch_labels = None
depends_on = None

task_names = [
    # Added in a76b9185b334
    "task_clean_up_tasks",
    "task_resume_workflows",
    # Added in 3c8b9185c221
    "task_validate_products",
    # Added in 961eddbd4c13
    "task_validate_subscriptions",
]


def upgrade() -> None:
    conn = op.get_bind()
    query = sa.text("UPDATE workflows SET is_task=true WHERE name = :task_name and is_task=false")
    for task_name in task_names:
        conn.execute(query, parameters={"task_name": task_name})


def downgrade() -> None:
    pass  # Does not make sense to downgrade back to a 'bad' state.
