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

"""Add AI search tables (from llm_migration.py).

Port of orchestrator/search/llm_migration.py into a proper alembic migration.
Creates the ai_search_index, agent_runs, search_queries, and graph_snapshots tables
along with required extensions and the field_type enum.

Revision ID: a1b2c3d4e5f6
Revises: fbc16e410bc6
Create Date: 2026-04-13 00:00:00.000000

"""

from alembic import op
from sqlalchemy import text

from orchestrator.search.core.types import FieldType
from orchestrator.settings import llm_settings

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "fbc16e410bc6"
branch_labels = None
depends_on = None

TABLE = "ai_search_index"
TARGET_DIM = llm_settings.EMBEDDING_DIMENSION


def upgrade() -> None:
    conn = op.get_bind()

    # Check for pgvector extension; create extensions if missing or forced
    res = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector' LIMIT 1;"))
    if llm_settings.LLM_FORCE_EXTENSION_MIGRATION or res.fetchone() is None:
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS ltree;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

    # Create field_type enum if not exists
    field_type_values = "', '".join([ft.value for ft in FieldType])
    create_enum_sql = f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'field_type') THEN
                CREATE TYPE field_type AS ENUM ('{field_type_values}');
            END IF;
        END $$;
    """  # noqa: S608
    conn.execute(text(create_enum_sql))

    # Create ai_search_index table with IF NOT EXISTS (for existing installations)
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                entity_type TEXT NOT NULL,
                entity_id UUID NOT NULL,
                entity_title TEXT,
                path LTREE NOT NULL,
                value TEXT NOT NULL,
                embedding VECTOR({TARGET_DIM}),
                content_hash VARCHAR(64) NOT NULL,
                value_type field_type NOT NULL DEFAULT '{FieldType.STRING.value}',
                CONSTRAINT pk_ai_search_index PRIMARY KEY (entity_id, path)
            );
            """
        )
    )

    # Drop default on value_type
    conn.execute(text(f"ALTER TABLE {TABLE} ALTER COLUMN value_type DROP DEFAULT;"))

    # Add entity_title column if it doesn't exist (backwards compat for existing installations)
    add_entity_title_sql = f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = '{TABLE}' AND column_name = 'entity_title'
            ) THEN
                ALTER TABLE {TABLE} ADD COLUMN entity_title TEXT;
            END IF;
        END $$;
    """  # noqa: S608
    conn.execute(text(add_entity_title_sql))

    # Create indexes for ai_search_index
    conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_ai_search_index_entity_id ON {TABLE} (entity_id);"))
    conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_ai_search_index_content_hash ON {TABLE} (content_hash);"))
    conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_flat_path_gist ON {TABLE} USING GIST (path gist_ltree_ops);"))
    conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_flat_path_btree ON {TABLE} (path);"))
    conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_flat_value_trgm ON {TABLE} USING GIN (value gin_trgm_ops);"))
    conn.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS ix_flat_embed_hnsw ON {TABLE}"
            " USING HNSW (embedding vector_l2_ops) WITH (m = 16, ef_construction = 64);"
        )
    )

    # Create agent_runs table
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS agent_runs (
                run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                agent_type VARCHAR(50) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_runs_created_at ON agent_runs (created_at);"))

    # Add thread_id column to agent_runs if it doesn't exist (backwards compat)
    conn.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'agent_runs' AND column_name = 'thread_id'
                ) THEN
                    ALTER TABLE agent_runs ADD COLUMN thread_id VARCHAR(255);
                    -- Set default value for existing rows
                    UPDATE agent_runs SET thread_id = run_id::text WHERE thread_id IS NULL;
                    ALTER TABLE agent_runs ALTER COLUMN thread_id SET NOT NULL;
                END IF;
            END $$;
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_runs_thread_id ON agent_runs (thread_id);"))

    # Create search_queries table
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS search_queries (
                query_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                run_id UUID,
                query_number INTEGER NOT NULL,
                parameters JSONB NOT NULL,
                query_embedding VECTOR({TARGET_DIM}),
                executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                CONSTRAINT fk_search_queries_run_id FOREIGN KEY (run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE
            );
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_search_queries_run_id ON search_queries (run_id);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_search_queries_executed_at ON search_queries (executed_at);"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_search_queries_query_id ON search_queries (query_id);"))

    # Create graph_snapshots table for pydantic-graph state persistence
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS graph_snapshots (
                snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                run_id UUID NOT NULL,
                sequence_number INTEGER NOT NULL,
                snapshot_data JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                CONSTRAINT fk_graph_snapshots_run_id FOREIGN KEY (run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE,
                CONSTRAINT uq_graph_snapshots_run_sequence UNIQUE (run_id, sequence_number)
            );
            """
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_graph_snapshots_run_id_sequence ON graph_snapshots (run_id, sequence_number);"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(text("DROP TABLE IF EXISTS graph_snapshots CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS search_queries CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS agent_runs CASCADE;"))
    conn.execute(text(f"DROP TABLE IF EXISTS {TABLE} CASCADE;"))
    conn.execute(text("DROP TYPE IF EXISTS field_type;"))
