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

"""Convert unlimited text fields to limited nullable strings and normalize empty subscription notes.

Revision ID: d69e10434a04
Revises: 9736496e3eba
Create Date: 2026-01-12 14:17:58.255515

"""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d69e10434a04"
down_revision = "9736496e3eba"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    revision_file_path = Path(__file__.replace(".py", "_upgrade.sql"))
    with open(revision_file_path) as f:
        conn.execute(sa.text(f.read()))


def downgrade() -> None:
    conn = op.get_bind()
    revision_file_path = Path(__file__.replace(".py", "_downgrade.sql"))
    with open(revision_file_path) as f:
        conn.execute(sa.text(f.read()))
