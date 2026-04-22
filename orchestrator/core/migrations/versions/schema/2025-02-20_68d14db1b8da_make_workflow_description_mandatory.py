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

"""Make workflow description mandatory.

Revision ID: 68d14db1b8da
Revises: bac6be6f2b4f
Create Date: 2025-02-20 16:39:34.889953

"""

import sqlalchemy as sa
from alembic import op
from structlog import get_logger

logger = get_logger(__name__)

# revision identifiers, used by Alembic.
revision = "68d14db1b8da"
down_revision = "fc5c993a4b4a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
        op.alter_column("workflows", "description", existing_type=sa.TEXT(), nullable=False)
    except sa.exc.IntegrityError:
        logger.error(
            "Unable to execute migrations due to missing descriptions in workflow table, please create a migration to backfill this column."
        )
        raise


def downgrade() -> None:
    op.alter_column("workflows", "description", existing_type=sa.TEXT(), nullable=True)
