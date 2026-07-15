# Deprecate TSV Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deprecate TSV search, make LLM search the default (non-optional), move runtime DB migration to alembic, and update the 5.0 upgrade guide.

**Architecture:** Remove the `SEARCH_ENABLED` feature flag so search is always on. Move the `search` pip extra into core dependencies. Convert the runtime `llm_migration.py` into a proper alembic migration. Add deprecation warnings to TSV query paths (REST + GraphQL). Keep TSV infrastructure in place for now (follow-up removal in 5.x).

**Tech Stack:** Python, SQLAlchemy, Alembic, FastAPI, Strawberry GraphQL, pgvector

**Issue:** https://github.com/workfloworchestrator/orchestrator-core/issues/1264

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `pyproject.toml` | Move `litellm` from `search` extra to core deps; remove `search` extra |
| Create | `orchestrator/migrations/versions/schema/2026-04-13_<rev>_add_ai_search_tables.py` | Alembic migration for all tables from `llm_migration.py` |
| Modify | `orchestrator/llm_settings.py` | Remove `SEARCH_ENABLED` and `LLM_FORCE_EXTENTION_MIGRATION` settings |
| Modify | `orchestrator/app.py` | Remove `SEARCH_ENABLED` gate around migration call; remove runtime migration block entirely |
| Modify | `orchestrator/api/api_v1/api.py` | Remove `SEARCH_ENABLED` gate; always register search router |
| Modify | `orchestrator/cli/main.py` | Remove `SEARCH_ENABLED` gate; always register search CLI commands |
| Modify | `orchestrator/workflows/steps.py` | Remove `SEARCH_ENABLED` guards in `refresh_subscription_search_index` and `refresh_process_search_index` |
| Modify | `orchestrator/workflows/tasks/cleanup_tasks_log.py` | Remove `SEARCH_ENABLED` guard in `cleanup_ai_search_index` |
| Modify | `orchestrator/api/helpers.py` | Add deprecation warning when TSV query path is used |
| Modify | `orchestrator/search/llm_migration.py` | Keep file but gut contents; add deprecation docstring pointing to alembic migration |
| Modify | `test/unit_tests/search/conftest.py` | Remove `SEARCH_ENABLED` skip logic |
| Modify | `test/integration_tests/search/conftest.py` | Remove `SEARCH_ENABLED` skip logic |
| Modify | `test/integration_tests/search/README.md` | Remove `SEARCH_ENABLED=true` from example commands |
| Modify | `test/unit_tests/workflows/tasks/test_clean_up_task_log.py` | Remove `SEARCH_ENABLED` branching; always test with search |
| Modify | `test/unit_tests/schemas/test_search_requests.py` | Remove `importorskip` for search extra |
| Modify | `.github/workflows/run-unit-tests.yml` | Remove `SEARCH_ENABLED` env var |
| Modify | `.github/workflows/run-llm-integration-tests.yml` | Remove `SEARCH_ENABLED` env var |
| Modify | `docs/guides/upgrading/5.0.md` | Add section 7: search migration, index initialization, embedding resize |
| Modify | `setup.cfg` | Remove/update `search` marker description |

---

### Task 1: Move `search` extra to core dependencies

**Files:**
- Modify: `pyproject.toml:78-85`

- [ ] **Step 1: Move litellm to core dependencies**

In `pyproject.toml`, move `litellm>=1.80.0` from `[project.optional-dependencies]` search extra into the `dependencies` list. Remove the `search` extra entirely.

```toml
# In [project.dependencies], add at the end of the list:
    "litellm>=1.80.0",
```

Remove:
```toml
search = [
    "litellm>=1.80.0",
]
```

- [ ] **Step 2: Update setup.cfg search marker**

In `setup.cfg`, update the `search` marker description:

```
	search: Tests that require search/indexing functionality
```

(Remove "and the search extra dependencies" since there is no longer a separate extra.)

- [ ] **Step 3: Remove importorskip in test**

In `test/unit_tests/schemas/test_search_requests.py`, remove the line:

```python
pytest.importorskip("orchestrator.search.core.types", reason="search extra not installed")
```

- [ ] **Step 4: Verify dependency resolution**

Run: `uv lock`
Expected: Lock file regenerates successfully with litellm in core deps.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock setup.cfg test/unit_tests/schemas/test_search_requests.py
git commit -m "Make search dependencies mandatory by moving litellm to core deps"
```

---

### Task 2: Create alembic migration for search tables

**Files:**
- Create: `orchestrator/migrations/versions/schema/2026-04-13_<rev>_add_ai_search_tables.py`
- Reference: `orchestrator/search/llm_migration.py` (source of truth for table definitions)

- [ ] **Step 1: Generate alembic revision**

Run: `cd /Users/boers001/Documents/SURF/projects/orchestrator-core && uv run alembic -c orchestrator/migrations/alembic.ini revision -m "add ai search tables"`

Note the generated revision ID and file path. The `down_revision` should be `fbc16e410bc6`.

- [ ] **Step 2: Write the migration**

Replace the generated file content with:

```python
"""Add AI search tables.

Moves the runtime llm_migration.py into a proper alembic migration.
Creates: ai_search_index, agent_runs, search_queries, graph_snapshots tables.
Creates: field_type enum, pgvector extension (when LLM_FORCE_EXTENTION_MIGRATION=true or extension missing).

Revision ID: <generated>
Revises: fbc16e410bc6
Create Date: 2026-04-13

"""

from alembic import op
from sqlalchemy import text

from orchestrator.llm_settings import llm_settings
from orchestrator.search.core.types import FieldType

# revision identifiers, used by Alembic.
revision = "<generated>"
down_revision = "fbc16e410bc6"
branch_labels = None
depends_on = None

TABLE = "ai_search_index"
TARGET_DIM = 1536


def upgrade() -> None:
    connection = op.get_bind()

    # Create extensions if missing or forced
    res = connection.execute(text("SELECT * FROM pg_extension WHERE extname = 'vector';"))
    if llm_settings.LLM_FORCE_EXTENTION_MIGRATION or res.rowcount == 0:
        connection.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS ltree;"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent;"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

    # Create field_type enum
    field_type_values = "', '".join(ft.value for ft in FieldType)
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

    # Create ai_search_index table
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
                value_type field_type NOT NULL,
                CONSTRAINT pk_ai_search_index PRIMARY KEY (entity_id, path)
            );
            """
        )
    )

    # Add entity_title column if missing (existing installations)
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

    # Indexes for ai_search_index
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_ai_search_index_entity_id ON {TABLE} (entity_id);"))
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS idx_ai_search_index_content_hash ON {TABLE} (content_hash);"))
    connection.execute(
        text(f"CREATE INDEX IF NOT EXISTS ix_flat_path_gist ON {TABLE} USING GIST (path gist_ltree_ops);")
    )
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_flat_path_btree ON {TABLE} (path);"))
    connection.execute(
        text(f"CREATE INDEX IF NOT EXISTS ix_flat_value_trgm ON {TABLE} USING GIN (value gin_trgm_ops);")
    )
    connection.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS ix_flat_embed_hnsw ON {TABLE} "
            f"USING HNSW (embedding vector_l2_ops) WITH (m = 16, ef_construction = 64);"
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

    # Add thread_id column to agent_runs (backwards compatible)
    connection.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'agent_runs' AND column_name = 'thread_id'
                ) THEN
                    ALTER TABLE agent_runs ADD COLUMN thread_id VARCHAR(255);
                    UPDATE agent_runs SET thread_id = run_id::text WHERE thread_id IS NULL;
                    ALTER TABLE agent_runs ALTER COLUMN thread_id SET NOT NULL;
                END IF;
            END $$;
            """
        )
    )
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_runs_thread_id ON agent_runs (thread_id);"))

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
                CONSTRAINT fk_search_queries_run_id
                    FOREIGN KEY (run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE
            );
            """
        )
    )
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_search_queries_run_id ON search_queries (run_id);"))
    connection.execute(
        text("CREATE INDEX IF NOT EXISTS ix_search_queries_executed_at ON search_queries (executed_at);")
    )
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_search_queries_query_id ON search_queries (query_id);"))

    # Create graph_snapshots table
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS graph_snapshots (
                snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                run_id UUID NOT NULL,
                sequence_number INTEGER NOT NULL,
                snapshot_data JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                CONSTRAINT fk_graph_snapshots_run_id
                    FOREIGN KEY (run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE,
                CONSTRAINT uq_graph_snapshots_run_sequence UNIQUE (run_id, sequence_number)
            );
            """
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_graph_snapshots_run_id_sequence "
            "ON graph_snapshots (run_id, sequence_number);"
        )
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS graph_snapshots CASCADE;")
    op.execute("DROP TABLE IF EXISTS search_queries CASCADE;")
    op.execute("DROP TABLE IF EXISTS agent_runs CASCADE;")
    op.execute("DROP TABLE IF EXISTS ai_search_index CASCADE;")
    op.execute("DROP TYPE IF EXISTS field_type;")
```

- [ ] **Step 3: Run the migration locally to verify**

Run: `uv run alembic -c orchestrator/migrations/alembic.ini upgrade head`
Expected: Migration runs successfully; tables are created.

- [ ] **Step 4: Commit**

```bash
git add orchestrator/migrations/versions/schema/2026-04-13_*_add_ai_search_tables.py
git commit -m "Add alembic migration for AI search tables (from llm_migration.py)"
```

---

### Task 3: Remove `SEARCH_ENABLED` from `LLMSettings`

**Files:**
- Modify: `orchestrator/llm_settings.py:36-59`

- [ ] **Step 1: Remove `SEARCH_ENABLED` field**

In `orchestrator/llm_settings.py`, remove this line from `LLMSettings`:

```python
    SEARCH_ENABLED: bool = False  # Enable search/indexing with embeddings
```

And remove the comment `# Feature flags for LLM functionality` above it (since that was the only feature flag).

Keep `LLM_FORCE_EXTENTION_MIGRATION` — it is still used by the alembic migration.

- [ ] **Step 2: Commit**

```bash
git add orchestrator/llm_settings.py
git commit -m "Remove SEARCH_ENABLED setting, search is now always enabled"
```

---

### Task 4: Remove runtime migration from `OrchestratorCore`

**Files:**
- Modify: `orchestrator/app.py:153-169`

- [ ] **Step 1: Remove the SEARCH_ENABLED migration block**

In `orchestrator/app.py`, remove the entire block (lines 154-169):

```python
        from orchestrator.llm_settings import llm_settings

        if llm_settings.SEARCH_ENABLED:
            logger.info("Running search migration")
            try:
                from orchestrator.search.llm_migration import run_migration

                with db.engine.begin() as connection:
                    run_migration(connection)
            except ImportError as e:
                logger.error(
                    "Unable to run search migration. Please install search dependencies: "
                    "`pip install orchestrator-core[search]`",
                    error=str(e),
                )
                raise
```

- [ ] **Step 2: Commit**

```bash
git add orchestrator/app.py
git commit -m "Remove runtime search migration from OrchestratorCore init"
```

---

### Task 5: Remove `SEARCH_ENABLED` gates from API, CLI, and workflows

**Files:**
- Modify: `orchestrator/api/api_v1/api.py:35,98-103`
- Modify: `orchestrator/cli/main.py:21,28-42`
- Modify: `orchestrator/workflows/steps.py:157,181`
- Modify: `orchestrator/workflows/tasks/cleanup_tasks_log.py:20,54-68`

- [ ] **Step 1: Always register search API router**

In `orchestrator/api/api_v1/api.py`, replace lines 35 and 98-103:

Remove `from orchestrator.llm_settings import llm_settings` import.

Replace:
```python
if llm_settings.SEARCH_ENABLED:
    from orchestrator.api.api_v1.endpoints import search

    api_router.include_router(
        search.router, prefix="/search", tags=["Core", "Search"], dependencies=[Depends(authorize)]
    )
```

With:
```python
from orchestrator.api.api_v1.endpoints import search

api_router.include_router(
    search.router, prefix="/search", tags=["Core", "Search"], dependencies=[Depends(authorize)]
)
```

- [ ] **Step 2: Always register search CLI commands**

In `orchestrator/cli/main.py`, replace lines 21 and 28-42:

Remove `from orchestrator.llm_settings import llm_settings` import.

Move the conditional imports to top-level and remove the `if` guard:

```python
from orchestrator.cli.search import index_llm, resize_embedding, search_explore, speedtest

app.add_typer(index_llm.app, name="index", help="(Re-)Index the search table.")
app.add_typer(search_explore.app, name="search", help="Try out different search types.")
app.add_typer(
    resize_embedding.app,
    name="embedding",
    help="Resize the vector dimension of the embedding column in the search table.",
)
app.add_typer(
    speedtest.app,
    name="speedtest",
    help="Search performance testing and analysis.",
)
```

- [ ] **Step 3: Remove SEARCH_ENABLED guard from workflow steps**

In `orchestrator/workflows/steps.py`, for `refresh_subscription_search_index` (around line 157), change:

```python
        if llm_settings.SEARCH_ENABLED and subscription:
            from orchestrator.search.core.types import EntityType
            from orchestrator.search.indexing import run_indexing_for_entity

            run_indexing_for_entity(EntityType.SUBSCRIPTION, str(subscription.subscription_id))
```

To:
```python
        if subscription:
            from orchestrator.search.core.types import EntityType
            from orchestrator.search.indexing import run_indexing_for_entity

            run_indexing_for_entity(EntityType.SUBSCRIPTION, str(subscription.subscription_id))
```

Similarly for `refresh_process_search_index` (around line 181), change:

```python
        if llm_settings.SEARCH_ENABLED and process_id:
```

To:
```python
        if process_id:
```

Remove the `from orchestrator.llm_settings import llm_settings` import from `steps.py` if no longer used elsewhere in the file.

- [ ] **Step 4: Remove SEARCH_ENABLED guard from cleanup task**

In `orchestrator/workflows/tasks/cleanup_tasks_log.py`, replace `cleanup_ai_search_index`:

```python
@step("Clean up ai_search_indexes")
def cleanup_ai_search_index(deleted_process_id_list: list) -> State:
    from orchestrator.db.models import AiSearchIndex
    from orchestrator.search.core.types import EntityType

    count = 0
    if deleted_process_id_list:
        count = (
            db.session.query(AiSearchIndex)
            .filter(AiSearchIndex.entity_type == EntityType.PROCESS)
            .filter(AiSearchIndex.entity_id.in_(deleted_process_id_list))
            .delete(synchronize_session=False)
        )

    return {"ai_search_index_rows_deleted": count}
```

Remove the `from orchestrator import llm_settings` import if no longer used.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/api/api_v1/api.py orchestrator/cli/main.py orchestrator/workflows/steps.py orchestrator/workflows/tasks/cleanup_tasks_log.py
git commit -m "Remove SEARCH_ENABLED gates from API, CLI, and workflow steps"
```

---

### Task 6: Add deprecation warning to TSV query path

**Files:**
- Modify: `orchestrator/api/helpers.py:59-71`

- [ ] **Step 1: Write the failing test**

Create or add to an existing test file. Since `add_subscription_search_query_filter` is in `orchestrator/api/helpers.py`, add a test:

```python
# In test/unit_tests/api/test_helpers.py (or create if needed)
import warnings

import pytest

from orchestrator.api.helpers import add_subscription_search_query_filter


def test_subscription_search_query_filter_emits_deprecation_warning(db_session):
    """TSV search should emit a deprecation warning pointing to LLM search."""
    from sqlalchemy import select

    from orchestrator.db import SubscriptionTable

    stmt = select(SubscriptionTable)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        add_subscription_search_query_filter(stmt, "test")
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) == 1
        assert "deprecated" in str(deprecation_warnings[0].message).lower()
        assert "search" in str(deprecation_warnings[0].message).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest test/unit_tests/api/test_helpers.py::test_subscription_search_query_filter_emits_deprecation_warning -v`
Expected: FAIL — no deprecation warning emitted yet.

- [ ] **Step 3: Add deprecation warning to TSV query filter**

In `orchestrator/api/helpers.py`, modify `add_subscription_search_query_filter`:

```python
import warnings

# ... existing imports ...

def add_subscription_search_query_filter(stmt: Select, search_query: str) -> Select:
    """Filters the Select statement on the contents of the query string.

    The Select statement should read from SubscriptionTable as a source.
    The query will first be converted from camelCase to snake_case before parsing.

    .. deprecated::
        TSV search is deprecated and will be removed in a future version.
        Use the LLM-powered search API at ``/api/search`` instead.
    """
    warnings.warn(
        "TSV search is deprecated and will be removed in a future version. "
        "Use the LLM-powered search API at /api/search instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    if len(search_query) > MAX_QUERY_STRING_LENGTH:
        raise_status(HTTPStatus.BAD_REQUEST, f"Max query length of {MAX_QUERY_STRING_LENGTH} characters exceeded.")

    ts_query = create_ts_query_string(search_query)
    return stmt.join(SubscriptionSearchView).filter(
        func.to_tsquery("simple", ts_query).op("@@")(SubscriptionSearchView.tsv)
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest test/unit_tests/api/test_helpers.py::test_subscription_search_query_filter_emits_deprecation_warning -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator/api/helpers.py test/unit_tests/api/test_helpers.py
git commit -m "Add deprecation warning to TSV search query filter"
```

---

### Task 7: Gut `llm_migration.py` and mark as deprecated

**Files:**
- Modify: `orchestrator/search/llm_migration.py`

- [ ] **Step 1: Replace file contents**

Replace the entire contents of `orchestrator/search/llm_migration.py` with:

```python
"""LLM search migration — DEPRECATED.

This module previously ran search table migrations at application startup.
These migrations are now managed by alembic. See:
    orchestrator/migrations/versions/schema/2026-04-13_*_add_ai_search_tables.py

This file is kept for backwards compatibility and will be removed in a future release.
"""

import warnings

from sqlalchemy.engine import Connection


def run_migration(connection: Connection) -> None:
    """No-op. Search migrations are now handled by alembic."""
    warnings.warn(
        "run_migration() is deprecated. Search table migrations are now managed by alembic. "
        "Run 'alembic upgrade head' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
```

- [ ] **Step 2: Commit**

```bash
git add orchestrator/search/llm_migration.py
git commit -m "Deprecate llm_migration.py, migrations now handled by alembic"
```

---

### Task 8: Update tests to remove SEARCH_ENABLED branching

**Files:**
- Modify: `test/unit_tests/search/conftest.py:49-56`
- Modify: `test/integration_tests/search/conftest.py:30-37`
- Modify: `test/integration_tests/search/README.md:8,16,30`
- Modify: `test/unit_tests/workflows/tasks/test_clean_up_task_log.py:8,63-98,107-134`
- Modify: `.github/workflows/run-unit-tests.yml:68`
- Modify: `.github/workflows/run-llm-integration-tests.yml:68`

- [ ] **Step 1: Remove SEARCH_ENABLED skip from unit test conftest**

In `test/unit_tests/search/conftest.py`, remove the entire `pytest_ignore_collect` function (lines 49-56):

```python
def pytest_ignore_collect(collection_path, config):
    """Ignore collecting tests from this directory when search is disabled."""
    from orchestrator.llm_settings import llm_settings

    # Skip this entire directory if search is disabled
    if not llm_settings.SEARCH_ENABLED:
        return True
    return False
```

- [ ] **Step 2: Remove SEARCH_ENABLED skip from integration test conftest**

In `test/integration_tests/search/conftest.py`, remove the `pytest_ignore_collect` function (lines 30-37):

```python
def pytest_ignore_collect(collection_path, config):
    """Ignore collecting tests from this directory when search is disabled."""
    from orchestrator.llm_settings import llm_settings

    # Skip this entire directory if search is disabled
    if not llm_settings.SEARCH_ENABLED:
        return True
    return False
```

- [ ] **Step 3: Update integration test README**

In `test/integration_tests/search/README.md`, remove `SEARCH_ENABLED=true` prefix from all commands:

```bash
# Before
SEARCH_ENABLED=true uv run pytest test/integration_tests/search/

# After
uv run pytest test/integration_tests/search/
```

Apply to all three occurrences (lines 8, 16, 30).

- [ ] **Step 4: Update cleanup task test to always test with search**

In `test/unit_tests/workflows/tasks/test_clean_up_task_log.py`:

Remove `from orchestrator import llm_settings` import.

In the `task` fixture, remove the `if llm_settings.SEARCH_ENABLED:` guard (lines 63-98). The search index setup should always run:

```python
    db.session.add_all([wf_old, wf_new, wf, generic_step, task_old, task_new, process])
    db.session.commit()

    from orchestrator.db.models import AiSearchIndex
    from orchestrator.search.core.types import EntityType, FieldType

    search_index_old_1 = AiSearchIndex(
        entity_type=EntityType.PROCESS,
        entity_id=task_old.process_id,
        entity_title="task_clean_up_task",
        path=Ltree("process.is_task"),
        value="True",
        content_hash="60c5df334e796463ac8865a83bcda791bb3ffb602585cfeca04bdb5ac5fab819",
        value_type=FieldType.BOOLEAN,
    )
    search_index_old_2 = AiSearchIndex(
        entity_type=EntityType.PROCESS,
        entity_id=task_old.process_id,
        entity_title="task_clean_up_task",
        path=Ltree("process.workflow_id"),
        value=task_old.workflow_id,
        content_hash="7cd393121fba5e804010654555d522af55f3b691838bc4fd8a7d6cd5a19177fe",
        value_type=FieldType.UUID,
    )
    non_matching_search_index = AiSearchIndex(
        entity_type=EntityType.PROCESS,
        entity_id=task_new.process_id,
        entity_title="task_clean_up_task",
        path=Ltree("process.is_task"),
        value="True",
        content_hash="50b5521b092f5d5d4add66add86de68549d47388c02e97cabc9e9696fba7320f",
        value_type=FieldType.BOOLEAN,
    )
    db.session.add_all([search_index_old_1, search_index_old_2, non_matching_search_index])
    db.session.commit()
```

In `test_remove_tasks`, remove the `if llm_settings.SEARCH_ENABLED:` / `else:` branching (lines 107-134). Keep only the search-enabled path:

```python
@pytest.mark.workflow
def test_remove_tasks(task):
    result, process, step_log = run_workflow("task_clean_up_tasks", {})
    assert_complete(result)
    res = extract_state(result)

    state = {
        "process_id": res["process_id"],
        "reporter": "john.doe",
        "tasks_removed": 1,
        "ai_search_index_rows_deleted": 2,
    }

    from orchestrator.db.models import AiSearchIndex

    ai_indexes = db.session.scalars(select(AiSearchIndex)).all()
    # 2 deleted, 1 left
    assert len(ai_indexes) == 1

    assert_state(result, state)
    assert len(res["deleted_process_id_list"]) == 1

    processes = db.session.scalars(select(ProcessTable)).all()

    assert len(processes) == 3
    assert sorted(p.workflow.name for p in processes) == sorted(
        ["nice and new task", "nice process", "task_clean_up_tasks"]
    )
```

- [ ] **Step 5: Remove SEARCH_ENABLED from CI workflows**

In `.github/workflows/run-unit-tests.yml`, remove line 68:
```yaml
          SEARCH_ENABLED: true
```

In `.github/workflows/run-llm-integration-tests.yml`, remove line 68:
```yaml
          SEARCH_ENABLED: true
```

- [ ] **Step 6: Run affected tests**

Run: `uv run pytest test/unit_tests/workflows/tasks/test_clean_up_task_log.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add test/unit_tests/search/conftest.py test/integration_tests/search/conftest.py test/integration_tests/search/README.md test/unit_tests/workflows/tasks/test_clean_up_task_log.py .github/workflows/run-unit-tests.yml .github/workflows/run-llm-integration-tests.yml
git commit -m "Remove SEARCH_ENABLED branching from all tests and CI"
```

---

### Task 9: Update 5.0 upgrade guide

**Files:**
- Modify: `docs/guides/upgrading/5.0.md`

- [ ] **Step 1: Add section 7 to upgrade guide**

Append after section 6 in `docs/guides/upgrading/5.0.md`:

```markdown
### 7. LLM-powered search is now the default

#### What changed

The LLM-powered search (AI search) is now a mandatory part of orchestrator-core. The following changes were made:

- **`SEARCH_ENABLED` setting removed** — search is always enabled. Remove this environment variable from your configuration.
- **`search` pip extra removed** — `litellm` is now a core dependency. Change `pip install orchestrator-core[search]` to just `pip install orchestrator-core`.
- **Search tables managed by alembic** — the `ai_search_index`, `agent_runs`, `search_queries`, and `graph_snapshots` tables are now created via an alembic migration instead of at application startup.
- **TSV search deprecated** — the `query` parameter on the subscriptions REST and GraphQL endpoints now emits a deprecation warning. Use the `/api/search` endpoint instead. TSV search will be removed in a future 5.x release.

#### What you need to do

**1. Prerequisites: install pgvector**

The `pgvector` PostgreSQL extension must be installed on your database server. If your database user has sufficient privileges, the migration will create the extension automatically. Otherwise, install it manually before running the migration:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

If your database user cannot create extensions but the extension already exists, no action is needed. If you need to force extension creation (e.g., after a PostgreSQL upgrade), set `LLM_FORCE_EXTENTION_MIGRATION=true`.

**2. Run the alembic migration**

```bash
alembic upgrade head
```

This creates the AI search tables. For existing installations that already have these tables (from the runtime migration), the migration uses `CREATE TABLE IF NOT EXISTS` and is safe to run.

**3. Configure your embedding provider**

Set the following environment variables:

```bash
OPENAI_API_KEY=sk-...          # Or your embedding provider's API key
EMBEDDING_MODEL=openai/text-embedding-3-small  # Default; see LiteLLM docs for alternatives
EMBEDDING_DIMENSION=1536       # Default; adjust based on your model
```

**4. Initialize the search index**

After the migration, populate the search index by running the CLI indexing commands:

```bash
python -m orchestrator.cli index subscriptions
python -m orchestrator.cli index products
python -m orchestrator.cli index processes
python -m orchestrator.cli index workflows
```

**5. (Optional) Resize embeddings**

If you want to use a different embedding dimension than the default (1536), update `EMBEDDING_DIMENSION` and run the resize command:

```bash
python -m orchestrator.cli embedding resize
```

!!! warning
    Resizing embeddings will **delete all existing embeddings** from `ai_search_index` and `search_queries` tables. You will need to re-index after resizing.

**6. Remove deprecated settings**

Remove these environment variables from your configuration:

- `SEARCH_ENABLED` — no longer used
- Any `pip install` commands that use `orchestrator-core[search]` — change to `orchestrator-core`
```

- [ ] **Step 2: Commit**

```bash
git add docs/guides/upgrading/5.0.md
git commit -m "Add LLM search migration section to 5.0 upgrade guide"
```

---

### Task 10: Final verification

- [ ] **Step 1: Run linting**

Run: `uv run ruff check orchestrator`
Expected: No errors.

- [ ] **Step 2: Run type checking**

Run: `uv run mypy orchestrator`
Expected: No new errors.

- [ ] **Step 3: Run unit tests**

Run: `uv run pytest test/unit_tests -x -v`
Expected: All tests pass.

- [ ] **Step 4: Grep for remaining SEARCH_ENABLED references**

Run a search for any remaining `SEARCH_ENABLED` references in application code (excluding migration files, git history):

```bash
grep -r "SEARCH_ENABLED" orchestrator/ test/ .github/ --include="*.py" --include="*.yml" --include="*.md"
```

Expected: No results except possibly the alembic migration docstring and the upgrade guide.

- [ ] **Step 5: Final commit if any fixes needed**

If any issues found, fix and commit.
