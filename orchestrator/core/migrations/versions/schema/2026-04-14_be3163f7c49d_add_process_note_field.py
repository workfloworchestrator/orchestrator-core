# Copyright 2019-2026 SURF, ESnet.
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
"""Add process note field.

Revision ID: be3163f7c49d
Revises: 262744958e0c
Create Date: 2026-04-14 19:56:14.971237

"""

import sqlalchemy as sa
from alembic import op

from orchestrator.core.db.models import StringThatAutoConvertsToNullWhenEmpty

# revision identifiers, used by Alembic.
revision = "be3163f7c49d"
down_revision = "262744958e0c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("processes", sa.Column("note", StringThatAutoConvertsToNullWhenEmpty(length=5000), nullable=True))


def downgrade() -> None:
    op.drop_column("processes", "note")
