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

"""Add ai_search_paths distinct-paths table maintained by a refcount trigger.

Speeds up GET /api/search/paths (issue #1788) by reading a schema-sized derived
table instead of GROUP BY-ing the whole ai_search_index EAV table.

Revision ID: ca79fd834ba0
Revises: f4a7c9e21b08
Create Date: 2026-07-15 00:00:00.000000

"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "ca79fd834ba0"
down_revision = "f4a7c9e21b08"
branch_labels = None
depends_on = None

TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION ai_search_paths_maintain() RETURNS trigger AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO ai_search_paths (entity_type, path, value_type, refcount)
        VALUES (NEW.entity_type, NEW.path, NEW.value_type, 1)
        ON CONFLICT (entity_type, path, value_type)
        DO UPDATE SET refcount = ai_search_paths.refcount + 1;
    ELSIF (TG_OP = 'DELETE') THEN
        UPDATE ai_search_paths SET refcount = refcount - 1
        WHERE entity_type = OLD.entity_type AND path = OLD.path AND value_type = OLD.value_type;
        DELETE FROM ai_search_paths
        WHERE entity_type = OLD.entity_type AND path = OLD.path AND value_type = OLD.value_type
          AND refcount <= 0;
    ELSIF (TG_OP = 'UPDATE') THEN
        IF (OLD.entity_type, OLD.path, OLD.value_type)
           IS DISTINCT FROM (NEW.entity_type, NEW.path, NEW.value_type) THEN
            UPDATE ai_search_paths SET refcount = refcount - 1
            WHERE entity_type = OLD.entity_type AND path = OLD.path AND value_type = OLD.value_type;
            DELETE FROM ai_search_paths
            WHERE entity_type = OLD.entity_type AND path = OLD.path AND value_type = OLD.value_type
              AND refcount <= 0;
            INSERT INTO ai_search_paths (entity_type, path, value_type, refcount)
            VALUES (NEW.entity_type, NEW.path, NEW.value_type, 1)
            ON CONFLICT (entity_type, path, value_type)
            DO UPDATE SET refcount = ai_search_paths.refcount + 1;
        END IF;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Derived distinct-paths table (schema-sized; PK covers entity_type filter + path ordering).
    #    No GIST/btree on path: the table is a few thousand rows, seq scan for `path ~ lquery` is instant.
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS ai_search_paths (
                entity_type TEXT NOT NULL,
                path LTREE NOT NULL,
                value_type field_type NOT NULL,
                refcount INTEGER NOT NULL,
                CONSTRAINT pk_ai_search_paths PRIMARY KEY (entity_type, path, value_type)
            );
            """
        )
    )

    # 2. Reference-counting trigger on ai_search_index.
    conn.execute(text(TRIGGER_FUNCTION))
    conn.execute(text("DROP TRIGGER IF EXISTS ai_search_paths_maintain_trg ON ai_search_index;"))
    conn.execute(
        text(
            "CREATE TRIGGER ai_search_paths_maintain_trg "
            "AFTER INSERT OR UPDATE OR DELETE ON ai_search_index "
            "FOR EACH ROW EXECUTE FUNCTION ai_search_paths_maintain();"
        )
    )

    # 3. Backfill from existing rows (idempotent). Writes ai_search_paths only, so the trigger is not involved.
    conn.execute(
        text(
            """
            INSERT INTO ai_search_paths (entity_type, path, value_type, refcount)
            SELECT entity_type, path, value_type, count(*)
            FROM ai_search_index
            GROUP BY entity_type, path, value_type
            ON CONFLICT (entity_type, path, value_type) DO NOTHING;
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TRIGGER IF EXISTS ai_search_paths_maintain_trg ON ai_search_index;"))
    conn.execute(text("DROP FUNCTION IF EXISTS ai_search_paths_maintain();"))
    conn.execute(text("DROP TABLE IF EXISTS ai_search_paths;"))
