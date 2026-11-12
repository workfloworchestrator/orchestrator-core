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

"""Add a check constraint that the fork columns are set together.

A fork step carries both ``branch_kind`` and ``branch_count``, an ordinary step neither.
``_create_fork_step`` inserts them in one statement, so every existing row already satisfies the
constraint and it is added as a plain validating constraint. That takes an ``ACCESS EXCLUSIVE`` lock
and a full scan of ``process_steps`` for the duration of this migration.

Revision ID: 06300482cd05
Revises: 18a7c2676fd3
Create Date: 2026-11-12 22:09:25.912607

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "06300482cd05"
down_revision = "18a7c2676fd3"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "ck_process_steps_branch_kind_count_set_together"


def upgrade() -> None:
    op.create_check_constraint(CONSTRAINT_NAME, "process_steps", "(branch_kind IS NULL) = (branch_count IS NULL)")


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "process_steps", type_="check")
