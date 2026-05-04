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

"""Add postgres function subscription_instance_as_json.

Revision ID: 42b3d076a85b
Revises: bac6be6f2b4f
Create Date: 2025-03-06 15:03:09.477225

"""

from pathlib import Path

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "42b3d076a85b"
down_revision = "bac6be6f2b4f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    revision_file_path = Path(__file__)
    with open(revision_file_path.with_suffix(".sql")) as f:
        conn.execute(text(f.read()))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(text("DROP FUNCTION IF EXISTS subscription_instance_as_json;"))
    conn.execute(text("DROP FUNCTION IF EXISTS subscription_instance_fields_as_json;"))
