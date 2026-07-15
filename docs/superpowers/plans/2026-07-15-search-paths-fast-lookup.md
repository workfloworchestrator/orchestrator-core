# Fast `/api/search/paths` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `GET /api/search/paths` fast by reading a small trigger-maintained distinct-paths table instead of `GROUP BY`-ing millions of EAV rows in `ai_search_index`.

**Architecture:** A new `ai_search_paths(entity_type, path, value_type, refcount)` table is kept exact by an `AFTER INSERT/UPDATE/DELETE` row trigger on `ai_search_index` that reference-counts each distinct tuple. `build_paths_query` reads this schema-sized (~thousands of rows) table. A `rebuild_search_paths()` recompute serves as the migration backfill and a drift-recovery CLI command.

**Tech Stack:** PostgreSQL (ltree, `field_type` enum, PL/pgSQL trigger), Alembic (raw-SQL migrations), SQLAlchemy 2.0 ORM, Typer CLI, pytest.

**Spec:** `docs/superpowers/specs/2026-07-15-search-paths-fast-lookup-design.md`
**Issue:** https://github.com/workfloworchestrator/orchestrator-core/issues/1788 — every commit message in this plan must reference `#1788`.

## Global Constraints

- Line length: **120**.
- **Absolute imports only** (`ban-relative-imports = "all"`) — no relative imports.
- Type annotations required everywhere (mypy strict).
- Google-style docstrings.
- Tests parametrized with `@pytest.mark.parametrize` + `pytest.param(..., id=...)`; never duplicate test functions that differ only in data.
- Prefer comprehensions/`itertools` over imperative loops; no `break`/`continue`.
- Commit messages: descriptive, reference `#1788`, **no** `Co-Authored-By` trailer.
- Do **not** use `git -c commit.gpgsign=false` — commit signing is via 1Password; if a commit blocks on GPG, wait for the unlock rather than disabling signing.

## File map

- **Create** `orchestrator/core/migrations/versions/schema/2026-07-15_1a2b3c4d5e6f_add_ai_search_paths_table.py` — table + trigger function + trigger + backfill (Task 1).
- **Modify** `orchestrator/core/search/indexing/tasks.py` — add `rebuild_search_paths()` (Task 2).
- **Modify** `orchestrator/core/search/indexing/__init__.py` — export `rebuild_search_paths` (Task 2).
- **Modify** `orchestrator/core/cli/search/index_llm.py` — add `rebuild-paths` command (Task 2).
- **Modify** `orchestrator/core/db/models.py` — add `AiSearchPaths` model (Task 3).
- **Modify** `orchestrator/core/search/query/builder.py` — repoint `build_paths_query` to `AiSearchPaths`, drop `GROUP BY` (Task 3).
- **Create** `test/integration_tests/search/test_ai_search_paths.py` — trigger, backfill, rebuild, and functional regression tests (Tasks 1–3).
- **Modify** `test/unit_tests/search/query/test_builder.py` — update the source-table / no-`GROUP BY` assertions (Task 3).

### Preflight

- [ ] **Step 0: Confirm the migration head is still `f4a7c9e21b08`.**

Run:
```bash
cd /Users/boers001/Documents/SURF/projects/orchestrator-core
uv run alembic -c orchestrator/core/migrations/alembic.ini heads 2>/dev/null || \
grep -rL "down_revision" orchestrator/core/migrations/versions/schema/*.py >/dev/null; \
python3 - <<'PY'
import re, pathlib
d = pathlib.Path("orchestrator/core/migrations/versions/schema")
revs, downs = {}, set()
for f in d.glob("*.py"):
    t = f.read_text()
    if m := re.search(r'^revision\s*=\s*["\']([^"\']+)', t, re.M): revs[m.group(1)] = f.name
    if m := re.search(r'^down_revision\s*=\s*["\']([^"\']+)', t, re.M): downs.add(m.group(1))
print("HEADS:", [(r, n) for r, n in revs.items() if r not in downs])
PY
```
Expected: exactly one head, `f4a7c9e21b08`. If it differs (main advanced), use the new head as `down_revision` in Task 1 and rename the migration date accordingly.

---

### Task 1: Migration — `ai_search_paths` table, refcount trigger, and backfill

**Files:**
- Create: `orchestrator/core/migrations/versions/schema/2026-07-15_1a2b3c4d5e6f_add_ai_search_paths_table.py`
- Test: `test/integration_tests/search/test_ai_search_paths.py`

**Interfaces:**
- Consumes: existing `ai_search_index` table, the `field_type` Postgres enum, and the `ltree` extension (all created by migration `262744958e0c`).
- Produces: table `ai_search_paths(entity_type TEXT, path LTREE, value_type field_type, refcount INTEGER)` with PK `(entity_type, path, value_type)`; trigger function `ai_search_paths_maintain()`; trigger `ai_search_paths_maintain_trg` on `ai_search_index`. After any DML on `ai_search_index`, `ai_search_paths` holds exactly one row per distinct `(entity_type, path, value_type)` with `refcount` = number of `ai_search_index` rows carrying that tuple.

- [ ] **Step 1: Write the failing integration tests.**

Create `test/integration_tests/search/test_ai_search_paths.py`:

```python
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

"""Integration tests for the trigger-maintained ai_search_paths distinct-paths table."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import FieldType


def _add_index_row(
    path: str,
    *,
    value_type: FieldType = FieldType.STRING,
    entity_type: str = "SUBSCRIPTION",
    entity_id: UUID | None = None,
    value: str = "v",
) -> UUID:
    """Insert one ai_search_index row (fires the maintain trigger) and return its entity_id."""
    eid = entity_id or uuid4()
    db.session.add(
        AiSearchIndex(
            entity_type=entity_type,
            entity_id=eid,
            path=Ltree(path),
            value=value,
            content_hash="0" * 64,
            value_type=value_type,
        )
    )
    db.session.flush()
    return eid


def _refcount(path: str, value_type: FieldType, entity_type: str = "SUBSCRIPTION") -> int | None:
    """Return the refcount for a tuple in ai_search_paths, or None if the row is absent."""
    row = db.session.execute(
        text(
            "SELECT refcount FROM ai_search_paths "
            "WHERE entity_type = :et AND path::text = :p AND value_type = CAST(:vt AS field_type)"
        ),
        {"et": entity_type, "p": path, "vt": value_type.value},
    ).fetchone()
    return row[0] if row else None


def test_insert_creates_path_with_refcount_one():
    _add_index_row("subscription.node.name")
    assert _refcount("subscription.node.name", FieldType.STRING) == 1


def test_second_entity_same_tuple_increments_refcount():
    _add_index_row("subscription.node.name")
    _add_index_row("subscription.node.name")
    assert _refcount("subscription.node.name", FieldType.STRING) == 2


def test_delete_one_of_two_keeps_row_at_one():
    first = _add_index_row("subscription.node.name")
    _add_index_row("subscription.node.name")
    db.session.query(AiSearchIndex).filter(AiSearchIndex.entity_id == first).delete(synchronize_session=False)
    db.session.flush()
    assert _refcount("subscription.node.name", FieldType.STRING) == 1


def test_delete_last_removes_row():
    eid = _add_index_row("subscription.node.name")
    db.session.query(AiSearchIndex).filter(AiSearchIndex.entity_id == eid).delete(synchronize_session=False)
    db.session.flush()
    assert _refcount("subscription.node.name", FieldType.STRING) is None


def test_update_value_type_moves_refcount_between_tuples():
    eid = _add_index_row("subscription.node.enabled", value_type=FieldType.STRING)
    db.session.query(AiSearchIndex).filter(AiSearchIndex.entity_id == eid).update(
        {"value_type": FieldType.BOOLEAN}, synchronize_session=False
    )
    db.session.flush()
    assert _refcount("subscription.node.enabled", FieldType.STRING) is None
    assert _refcount("subscription.node.enabled", FieldType.BOOLEAN) == 1


def test_reindex_same_tuple_is_noop():
    eid = _add_index_row("subscription.node.name", value="old")
    db.session.query(AiSearchIndex).filter(AiSearchIndex.entity_id == eid).update(
        {"value": "new"}, synchronize_session=False
    )
    db.session.flush()
    assert _refcount("subscription.node.name", FieldType.STRING) == 1


def test_distinct_tuples_tracked_separately():
    _add_index_row("subscription.node.name", entity_type="SUBSCRIPTION")
    _add_index_row("subscription.node.name", entity_type="PRODUCT")
    assert _refcount("subscription.node.name", FieldType.STRING, "SUBSCRIPTION") == 1
    assert _refcount("subscription.node.name", FieldType.STRING, "PRODUCT") == 1
```

- [ ] **Step 2: Run the tests to verify they fail.**

Run: `uv run pytest test/integration_tests/search/test_ai_search_paths.py -v`
Expected: FAIL — every test errors with `psycopg.errors.UndefinedTable: relation "ai_search_paths" does not exist` (the table/trigger are not created yet).

- [ ] **Step 3: Write the migration.**

Create `orchestrator/core/migrations/versions/schema/2026-07-15_1a2b3c4d5e6f_add_ai_search_paths_table.py`:

```python
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

Revision ID: 1a2b3c4d5e6f
Revises: f4a7c9e21b08
Create Date: 2026-07-15 00:00:00.000000

"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "1a2b3c4d5e6f"
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
```

- [ ] **Step 4: Run the tests to verify they pass.**

Run: `uv run pytest test/integration_tests/search/test_ai_search_paths.py -v`
Expected: PASS — all 7 tests green (the session-scoped `database` fixture re-runs `alembic upgrade heads`, creating the new table + trigger).

- [ ] **Step 5: Commit.**

```bash
git add orchestrator/core/migrations/versions/schema/2026-07-15_1a2b3c4d5e6f_add_ai_search_paths_table.py \
        test/integration_tests/search/test_ai_search_paths.py
git commit -m "Add ai_search_paths table + refcount trigger for fast /api/search/paths (#1788)"
```

---

### Task 2: `rebuild_search_paths()` recompute + CLI command

**Files:**
- Modify: `orchestrator/core/search/indexing/tasks.py`
- Modify: `orchestrator/core/search/indexing/__init__.py`
- Modify: `orchestrator/core/cli/search/index_llm.py`
- Test: `test/integration_tests/search/test_ai_search_paths.py` (append)

**Interfaces:**
- Consumes: `ai_search_paths` and `ai_search_index` from Task 1; `db` from `orchestrator.core.db`.
- Produces: `rebuild_search_paths() -> None` — truncates `ai_search_paths` and repopulates it with exact refcounts recomputed from `ai_search_index` in one statement; commits. Exported from `orchestrator.core.search.indexing`. CLI: `index rebuild-paths`.

- [ ] **Step 1: Write the failing rebuild test (append to the Task 1 test file).**

Append to `test/integration_tests/search/test_ai_search_paths.py`:

```python
from orchestrator.core.search.indexing import rebuild_search_paths


def _all_paths_rows() -> set[tuple]:
    """Return the full ai_search_paths contents as a comparable set."""
    rows = db.session.execute(
        text("SELECT entity_type, path::text, value_type::text, refcount FROM ai_search_paths")
    ).fetchall()
    return {tuple(r) for r in rows}


def _expected_paths_rows() -> set[tuple]:
    """Recompute the expected distinct-paths contents directly from ai_search_index."""
    rows = db.session.execute(
        text(
            "SELECT entity_type, path::text, value_type::text, count(*) "
            "FROM ai_search_index GROUP BY entity_type, path, value_type"
        )
    ).fetchall()
    return {tuple(r) for r in rows}


def test_rebuild_reconstructs_exact_table_after_drift():
    _add_index_row("subscription.node.name")
    _add_index_row("subscription.node.name")
    _add_index_row("subscription.node.speed", value_type=FieldType.INTEGER)

    # Corrupt the derived table: wrong refcount, a spurious row, and a missing row.
    db.session.execute(text("UPDATE ai_search_paths SET refcount = 99 WHERE path::text = 'subscription.node.name'"))
    db.session.execute(
        text(
            "INSERT INTO ai_search_paths (entity_type, path, value_type, refcount) "
            "VALUES ('SUBSCRIPTION', 'bogus.path'::ltree, CAST('string' AS field_type), 5)"
        )
    )
    db.session.execute(text("DELETE FROM ai_search_paths WHERE path::text = 'subscription.node.speed'"))
    db.session.flush()

    rebuild_search_paths()

    assert _all_paths_rows() == _expected_paths_rows()


def test_rebuild_on_empty_index_yields_empty_table():
    _add_index_row("subscription.node.name")
    db.session.query(AiSearchIndex).delete(synchronize_session=False)
    db.session.flush()
    rebuild_search_paths()
    assert _all_paths_rows() == set()
```

- [ ] **Step 2: Run the new tests to verify they fail.**

Run: `uv run pytest test/integration_tests/search/test_ai_search_paths.py -k rebuild -v`
Expected: FAIL — `ImportError: cannot import name 'rebuild_search_paths' from 'orchestrator.core.search.indexing'`.

- [ ] **Step 3: Implement `rebuild_search_paths()` in `tasks.py`.**

Add to `orchestrator/core/search/indexing/tasks.py` (place after the existing imports and `run_indexing_for_entity`; add `from sqlalchemy import text` and `from orchestrator.core.db import db` to the imports if not already present):

```python
def rebuild_search_paths() -> None:
    """Recompute the ai_search_paths distinct-paths table from ai_search_index.

    Truncates the derived table and repopulates it with exact reference counts in a
    single pass. Serves as the migration backfill logic and as a drift-recovery
    command if a refcount is ever corrupted (e.g. by manual DB surgery).
    """
    db.session.execute(text("TRUNCATE TABLE ai_search_paths"))
    db.session.execute(
        text(
            "INSERT INTO ai_search_paths (entity_type, path, value_type, refcount) "
            "SELECT entity_type, path, value_type, count(*) "
            "FROM ai_search_index GROUP BY entity_type, path, value_type"
        )
    )
    db.session.commit()
```

- [ ] **Step 4: Export it from the indexing package.**

In `orchestrator/core/search/indexing/__init__.py`, update to:

```python
from orchestrator.core.search.indexing.tasks import rebuild_search_paths, run_indexing_for_entity

__all__ = ["rebuild_search_paths", "run_indexing_for_entity"]
```

(Keep the existing import style; the current file uses `from .tasks import ...` — replace the relative import with the absolute form above to satisfy `ban-relative-imports`.)

- [ ] **Step 5: Add the CLI command.**

In `orchestrator/core/cli/search/index_llm.py`, change the import line to:

```python
from orchestrator.core.search.indexing import rebuild_search_paths, run_indexing_for_entity
```

and add this command (e.g. after `workflows_command`):

```python
@app.command("rebuild-paths")
def rebuild_paths_command() -> None:
    """Recompute the ai_search_paths distinct-paths table from ai_search_index."""
    rebuild_search_paths()
```

- [ ] **Step 6: Run the tests to verify they pass.**

Run: `uv run pytest test/integration_tests/search/test_ai_search_paths.py -k rebuild -v`
Expected: PASS — both rebuild tests green.

- [ ] **Step 7: Commit.**

```bash
git add orchestrator/core/search/indexing/tasks.py orchestrator/core/search/indexing/__init__.py \
        orchestrator/core/cli/search/index_llm.py test/integration_tests/search/test_ai_search_paths.py
git commit -m "Add rebuild_search_paths recompute + 'index rebuild-paths' CLI command (#1788)"
```

---

### Task 3: Point `build_paths_query` at `ai_search_paths`

**Files:**
- Modify: `orchestrator/core/db/models.py`
- Modify: `orchestrator/core/search/query/builder.py`
- Test: `test/unit_tests/search/query/test_builder.py` (update), `test/integration_tests/search/test_ai_search_paths.py` (append)

**Interfaces:**
- Consumes: `ai_search_paths` table (Task 1).
- Produces: `AiSearchPaths` ORM model (`orchestrator.core.db.models.AiSearchPaths`) with columns `entity_type`, `path`, `value_type`, `refcount`. `build_paths_query(entity_type, prefix=None, q=None) -> Select` now selects `AiSearchPaths.path, AiSearchPaths.value_type` (no `GROUP BY`); its `(path, value_type)` row shape and all callers (`list_paths`, GraphQL `resolve_search_paths`, MCP tools, `process_path_rows`) are unchanged.

- [ ] **Step 1: Add the `AiSearchPaths` model.**

In `orchestrator/core/db/models.py`, add directly after the `AiSearchIndex` class (all referenced names — `TEXT`, `Enum`, `Integer`, `PrimaryKeyConstraint`, `mapped_column`, `LtreeType`, `FieldType` — are already imported in this module):

```python
class AiSearchPaths(BaseModel):
    __tablename__ = "ai_search_paths"

    entity_type = mapped_column(TEXT, nullable=False)
    path = mapped_column(LtreeType, nullable=False)
    value_type = mapped_column(
        Enum(FieldType, name="field_type", values_callable=lambda obj: [e.value for e in obj]), nullable=False
    )
    refcount = mapped_column(Integer, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("entity_type", "path", "value_type", name="pk_ai_search_paths"),)
```

- [ ] **Step 2: Update the unit test that asserts `GROUP BY`, and add a source-table assertion.**

In `test/unit_tests/search/query/test_builder.py`, replace `test_build_paths_query_group_by_path_and_value_type` (lines 120-124) with:

```python
def test_build_paths_query_reads_distinct_paths_table_without_group_by():
    """Query reads the ai_search_paths table directly; rows are distinct, so no GROUP BY is needed."""
    stmt = build_paths_query(EntityType.SUBSCRIPTION)
    sql = str(stmt.compile()).lower()
    assert "ai_search_paths" in sql
    assert "ai_search_index" not in sql
    assert "group by" not in sql
```

(The other `test_build_paths_query_*` assertions — `~`, `similarity`, `order by`, `entity_type` value — remain valid and must still pass unchanged.)

- [ ] **Step 3: Run the unit tests to verify the updated one fails.**

Run: `uv run pytest test/unit_tests/search/query/test_builder.py -k build_paths_query -v`
Expected: FAIL — `test_build_paths_query_reads_distinct_paths_table_without_group_by` fails (compiled SQL still says `ai_search_index` and contains `group by`); the other paths-query tests still pass.

- [ ] **Step 4: Repoint `build_paths_query`.**

In `orchestrator/core/search/query/builder.py`, change the import on line 24 from:

```python
from orchestrator.core.db.models import AiSearchIndex
```
to:
```python
from orchestrator.core.db.models import AiSearchIndex, AiSearchPaths
```

and replace `build_paths_query` (lines 94-111) with:

```python
def build_paths_query(entity_type: EntityType, prefix: str | None = None, q: str | None = None) -> Select:
    """Build the query for retrieving paths and their value types for leaves/components processing.

    Reads the ai_search_paths distinct-paths table (one row per (entity_type, path, value_type)),
    so no GROUP BY is required.
    """
    stmt = select(AiSearchPaths.path, AiSearchPaths.value_type).where(AiSearchPaths.entity_type == entity_type.value)

    if prefix:
        lquery_pattern = create_path_autocomplete_lquery(prefix)
        ltree_filter = LtreeFilter(op=FilterOp.MATCHES_LQUERY, value=lquery_pattern)
        stmt = stmt.where(ltree_filter.to_expression(AiSearchPaths.path, path=""))

    if q:
        score = func.similarity(cast(AiSearchPaths.path, String), q)
        stmt = stmt.order_by(score.desc(), AiSearchPaths.path)
    else:
        stmt = stmt.order_by(AiSearchPaths.path)

    return stmt
```

(`AiSearchIndex` stays imported — other functions in this module still use it.)

- [ ] **Step 5: Run the unit tests to verify they pass.**

Run: `uv run pytest test/unit_tests/search/query/test_builder.py -k build_paths_query -v`
Expected: PASS — all `build_paths_query` unit tests green.

- [ ] **Step 6: Add a functional regression test (append to the integration test file).**

Append to `test/integration_tests/search/test_ai_search_paths.py`:

```python
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.query.builder import build_paths_query, process_path_rows


def test_build_paths_query_returns_leaves_and_components_from_trigger_table():
    # Two entities share the leaf path; a nested path contributes a component.
    _add_index_row("subscription.node.name", entity_id=uuid4())
    _add_index_row("subscription.node.name", entity_id=uuid4())
    _add_index_row("subscription.node.speed", value_type=FieldType.INTEGER)
    # A different entity_type must not leak into SUBSCRIPTION results.
    _add_index_row("product.other.field", entity_type="PRODUCT")

    stmt = build_paths_query(EntityType.SUBSCRIPTION)
    rows = db.session.execute(stmt).all()
    leaves, components = process_path_rows(rows)

    leaf_names = {leaf.name for leaf in leaves}
    component_names = {c.name for c in components}
    assert leaf_names == {"name", "speed"}
    assert component_names == {"node"}
    assert "field" not in leaf_names  # PRODUCT row excluded by the entity_type filter


@pytest.mark.parametrize(
    ("prefix", "expected_leaves"),
    [
        pytest.param("subscription.node", {"name"}, id="prefix-matches-node"),
        pytest.param("subscription.iface", set(), id="prefix-matches-nothing"),
    ],
)
def test_build_paths_query_prefix_filter(prefix, expected_leaves):
    _add_index_row("subscription.node.name")
    stmt = build_paths_query(EntityType.SUBSCRIPTION, prefix=prefix)
    leaves, _ = process_path_rows(db.session.execute(stmt).all())
    assert {leaf.name for leaf in leaves} == expected_leaves
```

- [ ] **Step 7: Run the full new integration test file + the builder unit tests.**

Run:
```bash
uv run pytest test/integration_tests/search/test_ai_search_paths.py test/unit_tests/search/query/test_builder.py -v
```
Expected: PASS — all trigger, rebuild, and functional-regression tests plus the builder unit tests green.

- [ ] **Step 8: Commit.**

```bash
git add orchestrator/core/db/models.py orchestrator/core/search/query/builder.py \
        test/unit_tests/search/query/test_builder.py test/integration_tests/search/test_ai_search_paths.py
git commit -m "Read /api/search/paths from ai_search_paths distinct-paths table (#1788)"
```

---

### Task 4: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Lint, format, type-check.**

Run:
```bash
uv run ruff format orchestrator test/integration_tests/search/test_ai_search_paths.py test/unit_tests/search/query/test_builder.py
uv run ruff check orchestrator
uv run mypy orchestrator
```
Expected: no errors. (`rebuild_search_paths` has a return annotation; the migration and model match existing typed patterns.)

- [ ] **Step 2: Run the search unit + integration suites.**

Run:
```bash
uv run pytest test/unit_tests/search -q
uv run pytest test/integration_tests/search -q
```
Expected: PASS. If the integration run reports "no such database"/connection errors, start Postgres and export `DATABASE_URI` per the project's integration-test setup before rerunning.

- [ ] **Step 3: Confirm the migration round-trips.**

Run (against a scratch/test DB, never production):
```bash
uv run alembic -c orchestrator/core/migrations/alembic.ini downgrade -1
uv run alembic -c orchestrator/core/migrations/alembic.ini upgrade head
```
Expected: downgrade drops the trigger, function, and table without error; upgrade recreates them and backfills. (Skip if no scratch DB is configured — Task 1's tests already exercise the upgrade via `alembic upgrade heads`.)

---

## Notes / deliberate scope decisions

- **Embedding-resize path needs no change.** `drop_all_embeddings()` issues `DELETE FROM ai_search_index`, a row-level DML delete that fires the trigger per row and correctly drains `ai_search_paths` to empty; the subsequent reindex refills it. `rebuild_search_paths()` is available as the CLI recovery button if ever needed. `# ponytail: not wiring rebuild into resize — the trigger already keeps it correct; only revisit if the per-row trigger cost on the rare wipe is measured to hurt.`
- **No extra indexes on `ai_search_paths`** — PK only. The table is schema-sized (~thousands of rows); seq scan for the `path ~ lquery` filter is sub-millisecond. Add `USING GIST (path gist_ltree_ops)` only if it grows large.
- **Full-reindex trigger cost** (per-row trigger fires during a full CLI reindex) is accepted; disabling the trigger + `rebuild_search_paths()` for bulk ops is a marked follow-up in the spec, not in this plan.

## Self-review

- **Spec coverage:** table + PK (Task 1) ✓; refcount trigger with INSERT/DELETE/UPDATE branches and remove-at-zero (Task 1) ✓; migration backfill (Task 1) ✓; `rebuild_search_paths()` as recompute + CLI drift-recovery button (Task 2) ✓; `build_paths_query` repointed, `GROUP BY` dropped, callers unchanged (Task 3) ✓; test plan — trigger cases, rebuild-from-truth, functional regression across prefix/entity_type, unit source-table assertion (Tasks 1–3) ✓; resize path explicitly reasoned about (Notes) ✓.
- **Placeholder scan:** none — every code and test block is complete.
- **Type consistency:** `rebuild_search_paths() -> None` defined in Task 2, imported identically in `__init__.py` and the CLI; `AiSearchPaths` columns (`entity_type, path, value_type, refcount`) match the migration DDL and the trigger's `ON CONFLICT (entity_type, path, value_type)`; `build_paths_query` keeps its `(path, value_type)` row shape that `process_path_rows` consumes.
