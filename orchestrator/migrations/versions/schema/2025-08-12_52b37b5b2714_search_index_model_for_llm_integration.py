"""Search index model for llm integration.

Revision ID: 52b37b5b2714
Revises: 850dccac3b02
Create Date: 2025-08-12 22:34:26.694750

"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql
from sqlalchemy_utils import LtreeType

from orchestrator.search.core.types import FieldType

# revision identifiers, used by Alembic.
revision = "52b37b5b2714"
down_revision = "850dccac3b02"
branch_labels = None
depends_on = None

TABLE = "ai_search_index"
IDX_EMBED_HNSW = "ix_flat_embed_hnsw"
IDX_PATH_GIST = "ix_flat_path_gist"
IDX_PATH_BTREE = "ix_flat_path_btree"
IDX_VALUE_TRGM = "ix_flat_value_trgm"
IDX_CONTENT_HASH = "idx_ai_search_index_content_hash"

TARGET_DIM = 1536


def upgrade() -> None:
    # Create PostgreSQL extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS ltree;")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Create the ai_search_index table
    op.create_table(
        TABLE,
        sa.Column("entity_type", sa.Text, nullable=False),
        sa.Column("entity_id", postgresql.UUID, nullable=False),
        sa.Column("path", LtreeType, nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("embedding", Vector(TARGET_DIM), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("entity_id", "path", name="pk_ai_search_index"),
    )

    field_type_enum = sa.Enum(*[ft.value for ft in FieldType], name="field_type")
    field_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        TABLE,
        sa.Column("value_type", field_type_enum, nullable=False, server_default=FieldType.STRING.value),
    )
    op.alter_column(TABLE, "value_type", server_default=None)

    op.create_index(op.f("ix_ai_search_index_entity_id"), TABLE, ["entity_id"], unique=False)
    op.create_index(IDX_CONTENT_HASH, TABLE, ["content_hash"])

    op.create_index(
        IDX_PATH_GIST,
        TABLE,
        ["path"],
        postgresql_using="GIST",
        postgresql_ops={"path": "gist_ltree_ops"},
    )
    op.create_index(IDX_PATH_BTREE, TABLE, ["path"])
    op.create_index(IDX_VALUE_TRGM, TABLE, ["value"], postgresql_using="GIN", postgresql_ops={"value": "gin_trgm_ops"})

    op.create_index(
        IDX_EMBED_HNSW,
        TABLE,
        ["embedding"],
        postgresql_using="HNSW",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_l2_ops"},
    )


def downgrade() -> None:
    # Drop all indexes
    op.drop_index(IDX_EMBED_HNSW, table_name=TABLE, if_exists=True)
    op.drop_index(IDX_VALUE_TRGM, table_name=TABLE, if_exists=True)
    op.drop_index(IDX_PATH_BTREE, table_name=TABLE, if_exists=True)
    op.drop_index(IDX_PATH_GIST, table_name=TABLE, if_exists=True)
    op.drop_index(IDX_CONTENT_HASH, table_name=TABLE, if_exists=True)
    op.drop_index(op.f("ix_ai_search_index_entity_id"), table_name=TABLE, if_exists=True)

    # Drop table and enum
    op.drop_table(TABLE, if_exists=True)
    field_type_enum = sa.Enum(name="field_type")
    field_type_enum.drop(op.get_bind(), checkfirst=True)
