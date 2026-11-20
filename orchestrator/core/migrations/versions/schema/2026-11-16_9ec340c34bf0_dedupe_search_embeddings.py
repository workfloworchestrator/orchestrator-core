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

"""Move the vectors of ai_search_index into ai_search_embeddings, one row per distinct text.

ai_search_index rows now point at their vector through embedding_hash, so identical text is stored once. The
backfill runs in SQL and makes no embedding API calls. In one transaction, the upgrade:

1. Creates ai_search_embeddings table.
2. Drops the old per-type HNSW indexes on ai_search_index.
3. Adds embedding_hash, computed from EMBEDDING_MODEL and the text, on every row where embedding is set.
4. Copies one vector per distinct hash into ai_search_embeddings.
5. Builds the per-type HNSW indexes on ai_search_embeddings.
6. Drops the embedding column and indexes ai_search_index on (entity_type, embedding_hash).

The hash is built over bytea because Postgres text cannot hold the NUL separator that the Python
``compute_embedding_hash`` uses. The model id comes from ``EMBEDDING_MODEL`` at migration time, so the migration
job must have it set, and the existing vectors are assumed to come from that model. The vector dimension is read
from the existing column, so ``EMBEDDING_DIMENSION`` only matters when that column has none.

The migration holds an ACCESS EXCLUSIVE lock on ai_search_index until it commits, which blocks the indexer and
searches. Run it in a maintenance window.

It does not shrink the table on disk. Run ``VACUUM FULL ai_search_index`` (or pg_repack) afterwards.

Downgrade is lossy: restored rows get the one stored vector for their text, and it assumes the same
``EMBEDDING_MODEL``.

Revision ID: 9ec340c34bf0
Revises: bfa6c728afd9
Create Date: 2026-11-16 16:17:07.306301

"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from orchestrator.core.settings import llm_settings

# revision identifiers, used by Alembic.
revision = "9ec340c34bf0"
down_revision = "bfa6c728afd9"
branch_labels = None
depends_on = None

INDEX_TABLE = "ai_search_index"
EMBEDDINGS_TABLE = "ai_search_embeddings"
# Spelled out rather than imported from EntityType: a migration must keep describing the schema it
# was written against, even if the enum gains or loses members later.
ENTITY_TYPES = ("SUBSCRIPTION", "PRODUCT", "WORKFLOW", "PROCESS")
JOIN_INDEX = "ix_ai_search_index_entity_type_embedding_hash"

# Same value as compute_embedding_hash(model, f"{path}: {value}"), see the module docstring for why bytea.
HASH_SQL = (
    "encode(sha256(convert_to(CAST(:model AS text), 'UTF8') || '\\x00'::bytea"
    " || convert_to(lower(path::text || ': ' || value), 'UTF8')), 'hex')"
)


def _old_index_name(entity_type: str) -> str:
    return f"ix_flat_embed_hnsw_{entity_type.lower()}"


def _new_index_name(entity_type: str) -> str:
    return f"ix_ai_search_embeddings_hnsw_{entity_type.lower()}"


def _vector_dimension(conn: sa.Connection, table: str, column: str) -> int:
    """Dimension of an existing vector column, or the setting when it has none.

    Reading it from the data keeps the migration working when EMBEDDING_DIMENSION differs from what was stored.
    """
    typmod = conn.execute(
        sa.text(
            "SELECT atttypmod FROM pg_attribute"
            " WHERE attrelid = CAST(:table AS regclass) AND attname = :column AND NOT attisdropped"
        ),
        {"table": table, "column": column},
    ).scalar()
    return typmod if typmod and typmod > 0 else llm_settings.EMBEDDING_DIMENSION


def _create_hnsw_index(name: str, table: str, predicate: str) -> None:
    op.create_index(
        name,
        table,
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_l2_ops"},
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_where=sa.text(predicate),
    )


def upgrade() -> None:
    conn = op.get_bind()
    dimension = _vector_dimension(conn, INDEX_TABLE, "embedding")

    op.create_table(
        EMBEDDINGS_TABLE,
        sa.Column("entity_type", sa.Text, nullable=False),
        sa.Column("embedding_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(dimension), nullable=False),
        sa.PrimaryKeyConstraint("entity_type", "embedding_hash", name="pk_ai_search_embeddings"),
    )

    # Before the UPDATE, otherwise every new row version it writes is also inserted into one of these HNSW indexes.
    # The loops in this migration run DDL for its side effect, they do not build a collection.
    for entity_type in ENTITY_TYPES:
        op.drop_index(_old_index_name(entity_type), table_name=INDEX_TABLE, if_exists=True)
    op.add_column(INDEX_TABLE, sa.Column("embedding_hash", sa.String(64), nullable=True))
    # The data statements stay SQL: the hash must match compute_embedding_hash byte for byte. The f-strings only
    # interpolate the module constants above.
    conn.execute(
        sa.text(f"UPDATE {INDEX_TABLE} SET embedding_hash = {HASH_SQL} WHERE embedding IS NOT NULL"),  # noqa: S608
        {"model": llm_settings.EMBEDDING_MODEL},
    )
    # DISTINCT ON without ORDER BY: any one vector per text will do, copies only differ by about 0.001 L2
    conn.execute(
        sa.text(
            f"INSERT INTO {EMBEDDINGS_TABLE} (entity_type, embedding_hash, embedding)"  # noqa: S608
            f" SELECT DISTINCT ON (entity_type, embedding_hash) entity_type, embedding_hash, embedding"
            f" FROM {INDEX_TABLE} WHERE embedding_hash IS NOT NULL"
        )
    )

    # After the backfill, so the index builds see the final rows instead of paying for every insert.
    for entity_type in ENTITY_TYPES:
        _create_hnsw_index(_new_index_name(entity_type), EMBEDDINGS_TABLE, f"entity_type = '{entity_type}'")
    op.drop_column(INDEX_TABLE, "embedding")
    op.create_index(JOIN_INDEX, INDEX_TABLE, ["entity_type", "embedding_hash"])


def downgrade() -> None:
    conn = op.get_bind()
    dimension = _vector_dimension(conn, EMBEDDINGS_TABLE, "embedding")

    op.add_column(INDEX_TABLE, sa.Column("embedding", Vector(dimension), nullable=True))
    conn.execute(
        sa.text(
            f"UPDATE {INDEX_TABLE} AS idx SET embedding = emb.embedding FROM {EMBEDDINGS_TABLE} AS emb"  # noqa: S608
            " WHERE emb.entity_type = idx.entity_type AND emb.embedding_hash = idx.embedding_hash"
        )
    )
    for entity_type in ENTITY_TYPES:
        _create_hnsw_index(
            _old_index_name(entity_type), INDEX_TABLE, f"entity_type = '{entity_type}' AND embedding IS NOT NULL"
        )
    op.drop_index(JOIN_INDEX, table_name=INDEX_TABLE, if_exists=True)
    op.drop_column(INDEX_TABLE, "embedding_hash")
    op.drop_table(EMBEDDINGS_TABLE)
