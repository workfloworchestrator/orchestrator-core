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

"""The migration that moves vectors from ai_search_index into the deduplicated ai_search_embeddings table.

Each test migrates a scratch database to the previous revision, seeds old-shape rows with raw SQL, and then runs
the migration under test. The shared test database is already at head so it cannot show the data move.
"""

from collections.abc import Iterator
from contextlib import closing, contextmanager
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine.url import make_url

from orchestrator.core.search.core.embedding import compute_embedding_hash
from orchestrator.core.settings import SecretPostgresDsn, app_settings, llm_settings
from orchestrator.core.testing.fixtures import make_alembic_config

PREVIOUS_REVISION = "bfa6c728afd9"
REVISION = "9ec340c34bf0"
ENTITY_TYPES = ("SUBSCRIPTION", "PRODUCT", "WORKFLOW", "PROCESS")
PROCESS_TEXT_PATH = "process.workflow_name"

pytestmark = pytest.mark.search


class Scratch:
    """A scratch database that can be moved between revisions."""

    def __init__(self, uri: str, config: Config) -> None:
        self.uri = uri
        self.config = config

    def migrate(self, revision: str, *, downgrade: bool = False) -> None:
        with patch.object(app_settings, "DATABASE_URI", SecretPostgresDsn(self.uri)):  # type: ignore[arg-type]
            (command.downgrade if downgrade else command.upgrade)(self.config, revision)

    @contextmanager
    def begin(self) -> Iterator[Connection]:
        engine = create_engine(self.uri)
        try:
            with engine.begin() as conn:
                yield conn
        finally:
            engine.dispose()


@pytest.fixture
def scratch(db_uri: str) -> Iterator[Scratch]:
    url = make_url(db_uri)
    scratch_name = f"{url.database}-dedupe-migration"
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with closing(admin.connect()) as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch_name}"'))
        conn.execute(text(f'CREATE DATABASE "{scratch_name}" TEMPLATE template0'))
    scratch_uri = url.set(database=scratch_name).render_as_string(hide_password=False)
    scratch_db = Scratch(scratch_uri, make_alembic_config(scratch_uri))
    try:
        yield scratch_db
    finally:
        with closing(admin.connect()) as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch_name}" WITH (FORCE)'))
        admin.dispose()


def _vector(seed: float) -> str:
    """A pgvector literal of the configured dimension that differs a little per seed."""
    return "[" + ",".join(str(seed if i == 0 else 0.0) for i in range(llm_settings.EMBEDDING_DIMENSION)) + "]"


def _old_row(entity_type: str, path: str, value: str, embedding: str | None) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "entity_id": str(uuid4()),
        "path": path,
        "value": value,
        "embedding": embedding,
        "content_hash": uuid4().hex,
    }


def _insert_old_rows(conn: Connection, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    conn.execute(
        text(
            "INSERT INTO ai_search_index (entity_type, entity_id, entity_title, path, value, value_type, embedding,"
            " content_hash) VALUES (:entity_type, :entity_id, 'title', CAST(:path AS ltree), :value, 'string',"
            " CAST(:embedding AS vector), :content_hash)"
        ),
        rows,
    )


def _upgraded(scratch: Scratch, rows: list[dict[str, Any]]) -> None:
    scratch.migrate(PREVIOUS_REVISION)
    with scratch.begin() as conn:
        _insert_old_rows(conn, rows)
    scratch.migrate(REVISION)


def _scalar(scratch: Scratch, sql: str) -> Any:
    with scratch.begin() as conn:
        return conn.execute(text(sql)).scalar_one()


def _rows(scratch: Scratch, sql: str) -> list[Any]:
    with scratch.begin() as conn:
        return list(conn.execute(text(sql)).all())


def test_backfill_dedupes_and_hashes(scratch: Scratch) -> None:
    same_text = [
        _old_row("PROCESS", PROCESS_TEXT_PATH, "Create Port", _vector(0.5 + i / 1000)) for i in range(3)
    ]  # slightly different vectors for one text, as the embedding API is not deterministic
    other_text = _old_row("PROCESS", PROCESS_TEXT_PATH, "Modify Port", _vector(0.9))
    failed_earlier = _old_row("PROCESS", PROCESS_TEXT_PATH, "Terminate Port", None)

    _upgraded(scratch, [*same_text, other_text, failed_earlier])

    expected = compute_embedding_hash(llm_settings.EMBEDDING_MODEL, f"{PROCESS_TEXT_PATH}: Create Port")
    hashes = dict(_rows(scratch, "SELECT value, embedding_hash FROM ai_search_index"))
    assert _scalar(scratch, "SELECT count(*) FROM ai_search_embeddings") == 2
    assert [hashes["Create Port"]] * 3 == [
        r[0] for r in _rows(scratch, "SELECT embedding_hash FROM ai_search_index WHERE value = 'Create Port'")
    ]
    assert hashes["Create Port"] == expected
    assert hashes["Modify Port"] == compute_embedding_hash(
        llm_settings.EMBEDDING_MODEL, f"{PROCESS_TEXT_PATH}: Modify Port"
    )
    assert hashes["Terminate Port"] is None
    assert (
        _scalar(
            scratch,
            "SELECT count(*) FROM information_schema.columns"
            " WHERE table_name = 'ai_search_index' AND column_name = 'embedding'",
        )
        == 0
    )


def test_sql_hash_matches_python_hash(scratch: Scratch) -> None:
    """The backfill computes the hash in SQL, so a mismatch would silently re-embed every row."""
    _upgraded(scratch, [_old_row("SUBSCRIPTION", "subscription.description", "Coffee Grinder CG-2000", _vector(0.1))])

    stored = _scalar(scratch, "SELECT embedding_hash FROM ai_search_index")
    assert stored == compute_embedding_hash(
        llm_settings.EMBEDDING_MODEL, "subscription.description: Coffee Grinder CG-2000"
    )
    assert _scalar(scratch, "SELECT embedding_hash FROM ai_search_embeddings") == stored


def test_same_text_two_entity_types_stored_twice(scratch: Scratch) -> None:
    _upgraded(
        scratch,
        [
            _old_row("SUBSCRIPTION", "shared.status", "active", _vector(0.2)),
            _old_row("PROCESS", "shared.status", "active", _vector(0.2)),
        ],
    )

    assert sorted(_rows(scratch, "SELECT entity_type FROM ai_search_embeddings")) == [("PROCESS",), ("SUBSCRIPTION",)]


def test_upgrade_moves_the_per_type_hnsw_indexes(scratch: Scratch) -> None:
    _upgraded(scratch, [])

    definitions = dict(_rows(scratch, "SELECT indexname, indexdef FROM pg_indexes WHERE indexdef ILIKE '%hnsw%'"))
    assert set(definitions) == {f"ix_ai_search_embeddings_hnsw_{t.lower()}" for t in ENTITY_TYPES}
    assert all(
        f"WHERE (entity_type = '{t}'::text)" in definitions[f"ix_ai_search_embeddings_hnsw_{t.lower()}"]
        for t in ENTITY_TYPES
    )
    assert all("ON public.ai_search_embeddings" in definition for definition in definitions.values())


def test_downgrade_restores_vectors(scratch: Scratch) -> None:
    rows = [
        _old_row("PROCESS", PROCESS_TEXT_PATH, "Create Port", _vector(0.5)),
        _old_row("PROCESS", PROCESS_TEXT_PATH, "Create Port", _vector(0.501)),
        _old_row("SUBSCRIPTION", "subscription.status", "active", None),
    ]
    _upgraded(scratch, rows)

    scratch.migrate(PREVIOUS_REVISION, downgrade=True)

    restored = dict(_rows(scratch, "SELECT value, embedding IS NOT NULL FROM ai_search_index"))
    assert restored == {"Create Port": True, "active": False}
    assert _scalar(scratch, "SELECT to_regclass('ai_search_embeddings') IS NULL")
    definitions = dict(_rows(scratch, "SELECT indexname, indexdef FROM pg_indexes WHERE indexdef ILIKE '%hnsw%'"))
    assert set(definitions) == {f"ix_flat_embed_hnsw_{t.lower()}" for t in ENTITY_TYPES}
    assert all(
        f"entity_type = '{t}'::text" in definitions[f"ix_flat_embed_hnsw_{t.lower()}"]
        and "embedding IS NOT NULL" in definitions[f"ix_flat_embed_hnsw_{t.lower()}"]
        and "ON public.ai_search_index" in definitions[f"ix_flat_embed_hnsw_{t.lower()}"]
        for t in ENTITY_TYPES
    )
    assert (
        _scalar(
            scratch,
            "SELECT count(*) FROM information_schema.columns"
            " WHERE table_name = 'ai_search_index' AND column_name = 'embedding_hash'",
        )
        == 0
    )


def test_dimension_comes_from_the_existing_column(scratch: Scratch) -> None:
    """A migration job whose EMBEDDING_DIMENSION differs from the stored vectors must neither fail nor resize them."""
    stored_dimension = 8 if llm_settings.EMBEDDING_DIMENSION != 8 else 16
    scratch.migrate(PREVIOUS_REVISION)
    with scratch.begin() as conn:
        conn.execute(text(f"ALTER TABLE ai_search_index ALTER COLUMN embedding TYPE vector({stored_dimension})"))
        stored_vector = "[" + ",".join(["0.1"] * stored_dimension) + "]"
        _insert_old_rows(conn, [_old_row("PROCESS", PROCESS_TEXT_PATH, "Create Port", stored_vector)])

    scratch.migrate(REVISION)

    typmod = "SELECT atttypmod FROM pg_attribute WHERE attrelid = CAST('{}' AS regclass) AND attname = 'embedding'"
    assert _scalar(scratch, typmod.format("ai_search_embeddings")) == stored_dimension
    assert _scalar(scratch, "SELECT count(*) FROM ai_search_embeddings") == 1

    scratch.migrate(PREVIOUS_REVISION, downgrade=True)

    assert _scalar(scratch, typmod.format("ai_search_index")) == stored_dimension
