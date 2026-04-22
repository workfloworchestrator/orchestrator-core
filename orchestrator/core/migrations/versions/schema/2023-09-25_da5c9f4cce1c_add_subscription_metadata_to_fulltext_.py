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

"""Add subscription metadata to fulltext search index.

Revision ID: da5c9f4cce1c
Revises: 165303a20fb1
Create Date: 2023-09-25 10:23:13.520977

"""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "da5c9f4cce1c"
down_revision = "165303a20fb1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    revision_file_path = Path(__file__)
    with open(revision_file_path.with_suffix(".sql")) as f:
        conn.execute(sa.text(f.read()))


def downgrade() -> None:
    """This migration is irreversible!

    Once the type of `subscriptions.customer_id` has been changed
    from UUID to VARCHAR, it is not a failsafe operation to convert whatever value `customer_id` might now hold
    into a valid UUID type.

    In future, it will be necessary for downstream users to implement their own schema & data migrations
    if they want to (or even feasibly can) change the type of the `customer_id` column.
    """
    pass
