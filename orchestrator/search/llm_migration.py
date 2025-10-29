# Copyright 2019-2025 SURF
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

"""Simple search migration function that runs when SEARCH_ENABLED = True."""

import pydantic_ai
from sqlalchemy import text
from sqlalchemy.engine import Connection
from structlog import get_logger

from orchestrator.llm_settings import llm_settings
from orchestrator.search.core.types import FieldType

logger = get_logger(__name__)

TABLE = "ai_search_index"
TARGET_DIM = 1536


def run_migration(connection: Connection) -> None:
    """Run LLM migration with ON CONFLICT DO NOTHING pattern."""
    logger.info("Running LLM migration", pydantic_ai_version=pydantic_ai.__version__)

    try:
        # Test to see if the extenstion exists and then skip the migration; Needed for certain situations where db user
        # has insufficient priviledges to run the `CREATE EXTENSION ...` command.
        res = connection.execute(text("SELECT * FROM pg_extension where extname = 'vector';"))
        if llm_settings.LLM_FORCE_EXTENTION_MIGRATION or res.rowcount == 0:
            # Create PostgreSQL extensions
            logger.info("Attempting to run the extention creation;")
            connection.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS ltree;"))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent;"))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        # Create field_type enum
        field_type_values = "', '".join([ft.value for ft in FieldType])
        connection.execute(
            text(
                f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'field_type') THEN
                    CREATE TYPE field_type AS ENUM ('{field_type_values}');
                END IF;
            END $$;
        """
            )
        )

        # Create table with ON CONFLICT DO NOTHING pattern
        connection.execute(
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

        # Drop default
        connection.execute(text(f"ALTER TABLE {TABLE} ALTER COLUMN value_type DROP DEFAULT;"))

        # Add entity_title column if it doesn't exist (for existing installations)
        connection.execute(
            text(
                f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = '{TABLE}' AND column_name = 'entity_title'
                ) THEN
                    ALTER TABLE {TABLE} ADD COLUMN entity_title TEXT;
                END IF;
            END $$;
        """
            )
        )

        # Create indexes with IF NOT EXISTS
        connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_ai_search_index_entity_id ON {TABLE} (entity_id);"))
        connection.execute(
            text(f"CREATE INDEX IF NOT EXISTS idx_ai_search_index_content_hash ON {TABLE} (content_hash);")
        )
        connection.execute(
            text(f"CREATE INDEX IF NOT EXISTS ix_flat_path_gist ON {TABLE} USING GIST (path gist_ltree_ops);")
        )
        connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_flat_path_btree ON {TABLE} (path);"))
        connection.execute(
            text(f"CREATE INDEX IF NOT EXISTS ix_flat_value_trgm ON {TABLE} USING GIN (value gin_trgm_ops);")
        )
        connection.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS ix_flat_embed_hnsw ON {TABLE} USING HNSW (embedding vector_l2_ops) WITH (m = 16, ef_construction = 64);"
            )
        )

        # Create agent_runs table
        connection.execute(
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
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_runs_created_at ON agent_runs (created_at);"))

        # Create search_queries table
        connection.execute(
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
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_search_queries_run_id ON search_queries (run_id);"))
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_search_queries_executed_at ON search_queries (executed_at);")
        )
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_search_queries_query_id ON search_queries (query_id);"))

        connection.commit()
        logger.info("LLM migration completed successfully")

    except Exception as e:
        logger.error("LLM migration failed", error=str(e))
        raise Exception(
            f"LLM migration failed. This likely means the pgvector extension "
            f"is not installed. Please install pgvector and ensure your PostgreSQL "
            f"version supports it. Error: {e}"
        ) from e
