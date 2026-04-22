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

"""Add product_block_relations.

Revision ID: 6896a54e9483
Revises: 3c8b9185c221
Create Date: 2021-07-01 15:33:38.065653

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy_utils import UUIDType

# revision identifiers, used by Alembic.
revision = "6896a54e9483"
down_revision = "3c8b9185c221"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_block_relations",
        sa.Column("parent_id", UUIDType(), nullable=False),
        sa.Column("child_id", UUIDType(), nullable=False),
        sa.Column("min", sa.Integer(), nullable=True),
        sa.Column("max", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["product_blocks.product_block_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["product_blocks.product_block_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("parent_id", "child_id"),
    )
    op.create_index("product_block_relation_p_c_ix", "product_block_relations", ["parent_id", "child_id"], unique=True)


def downgrade() -> None:
    op.drop_index("product_block_relation_p_c_ix", table_name="product_block_relations")
    op.drop_table("product_block_relations")
