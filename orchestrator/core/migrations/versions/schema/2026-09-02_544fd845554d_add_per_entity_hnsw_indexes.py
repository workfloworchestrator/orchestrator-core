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

"""Replace the single HNSW index on ai_search_index.embedding with one partial index per entity type.

The hybrid retriever reads its semantic candidates with ``ORDER BY embedding <-> query LIMIT n``
restricted to one entity type. On a shared index that restriction is a post-filter: the scan walks
the nearest vectors of *all* entity types and, when process rows dominate the index, can exhaust
its candidate frontier before it meets a single subscription, returning nothing. A partial index
per entity type makes the scan walk only that type's vectors.

Revision ID: 544fd845554d
Revises: ca79fd834ba0
Create Date: 2026-09-02 00:00:00.000000
"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "544fd845554d"
down_revision = "ca79fd834ba0"
branch_labels = None
depends_on = None

TABLE = "ai_search_index"
ENTITY_TYPES = ("SUBSCRIPTION", "PRODUCT", "WORKFLOW", "PROCESS")
HNSW_OPTIONS = "USING HNSW (embedding vector_l2_ops) WITH (m = 16, ef_construction = 64)"


def _partial_index_name(entity_type: str) -> str:
    return f"ix_flat_embed_hnsw_{entity_type.lower()}"


def upgrade() -> None:
    conn = op.get_bind()
    for entity_type in ENTITY_TYPES:
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {_partial_index_name(entity_type)} ON {TABLE} {HNSW_OPTIONS}"
                f" WHERE entity_type = '{entity_type}' AND embedding IS NOT NULL;"
            )
        )
    conn.execute(text("DROP INDEX IF EXISTS ix_flat_embed_hnsw;"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_flat_embed_hnsw ON {TABLE} {HNSW_OPTIONS};"))
    for entity_type in ENTITY_TYPES:
        conn.execute(text(f"DROP INDEX IF EXISTS {_partial_index_name(entity_type)};"))
