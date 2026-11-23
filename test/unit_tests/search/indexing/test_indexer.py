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

"""Tests for the Indexer class and helper functions (_maybe_begin, _maybe_progress).

Covers run() chunking, _process_chunk execution, batched deletes, hash retrieval,
upsert batch generation, buffer flushing, max token resolution, content hashing,
and indexable record creation.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.search.core.embedding import compute_embedding_hash
from orchestrator.core.search.core.types import EmbeddingRecord, EntityType, ExtractedField, FieldType, IndexableRecord
from orchestrator.core.search.indexing.indexer import IndexBatch, Indexer, StoredHashes, _maybe_begin, _maybe_progress

pytestmark = pytest.mark.search

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENTITY_ID = "12345678-1234-1234-1234-123456789abc"
ENTITY_TITLE = "Test Entity"
EMBEDDING_MODEL = "openai/text-embedding-3-small"


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_fields() -> list[ExtractedField]:
    return [
        ExtractedField(path="root.description", value="Some text value", value_type=FieldType.STRING),
        ExtractedField(path="root.status", value="active", value_type=FieldType.STRING),
        ExtractedField(path="root.insync", value="true", value_type=FieldType.BOOLEAN),
    ]


@pytest.fixture
def mock_entity() -> MagicMock:
    entity = MagicMock()
    entity.subscription_id = UUID(ENTITY_ID)
    return entity


@pytest.fixture
def mock_config(mock_fields: list[ExtractedField]) -> MagicMock:
    config = MagicMock()
    config.entity_kind = EntityType.SUBSCRIPTION
    config.pk_name = "subscription_id"
    config.root_name = "subscription"
    config.traverser.get_fields.return_value = mock_fields
    config.get_title_from_fields.return_value = ENTITY_TITLE
    return config


@pytest.fixture
def indexer(mock_config: MagicMock) -> Indexer:
    inst = Indexer(config=mock_config, dry_run=True, force_index=False, chunk_size=10)
    inst._entity_titles[ENTITY_ID] = ENTITY_TITLE
    return inst


def _make_indexer(mock_config: MagicMock, dry_run: bool = True, chunk_size: int = 10) -> Indexer:
    return Indexer(config=mock_config, dry_run=dry_run, force_index=False, chunk_size=chunk_size)


def _embeddable_field(path: str = "root.description", value: str = "Hello world") -> ExtractedField:
    return ExtractedField(path=path, value=value, value_type=FieldType.STRING)


def _non_embeddable_field(path: str = "root.insync", value: str = "true") -> ExtractedField:
    return ExtractedField(path=path, value=value, value_type=FieldType.BOOLEAN)


def _record(entity_id: str, embedding_hash: str | None) -> IndexableRecord:
    return {
        "entity_id": entity_id,
        "entity_type": EntityType.SUBSCRIPTION.value,
        "entity_title": ENTITY_TITLE,
        "path": Ltree(f"root.{entity_id}"),
        "value": "v",
        "value_type": FieldType.STRING,
        "content_hash": "abc",
        "embedding_hash": embedding_hash,
    }


# ---------------------------------------------------------------------------
# _maybe_begin
# ---------------------------------------------------------------------------


def test_maybe_begin_session_none_yields_without_begin() -> None:
    """When session is None, the context manager must yield without calling begin()."""
    with _maybe_begin(None):
        pass  # must not raise


def test_maybe_begin_session_not_none_calls_begin() -> None:
    """When a session is provided, begin() must be used as a context manager."""
    mock_session = MagicMock()
    mock_begin_ctx = MagicMock()
    mock_begin_ctx.__enter__ = MagicMock(return_value=None)
    mock_begin_ctx.__exit__ = MagicMock(return_value=False)
    mock_session.begin.return_value = mock_begin_ctx

    with _maybe_begin(mock_session):
        pass

    mock_session.begin.assert_called_once()
    mock_begin_ctx.__enter__.assert_called_once()
    mock_begin_ctx.__exit__.assert_called_once()


# ---------------------------------------------------------------------------
# _maybe_progress
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "total_count",
    [
        pytest.param(10, id="with_count"),
        pytest.param(None, id="none_count"),
    ],
)
def test_maybe_progress_false_yields_none(total_count: int | None) -> None:
    with _maybe_progress(False, total_count=total_count, label="Test") as progress:
        assert progress is None


def test_maybe_progress_true_yields_progress_bar() -> None:
    mock_bar = MagicMock()
    mock_progressbar_ctx = MagicMock()
    mock_progressbar_ctx.__enter__ = MagicMock(return_value=mock_bar)
    mock_progressbar_ctx.__exit__ = MagicMock(return_value=False)

    with patch("typer.progressbar", return_value=mock_progressbar_ctx) as mock_pb:
        with _maybe_progress(True, total_count=5, label="Indexing stuff") as progress:
            assert progress is mock_bar

        mock_pb.assert_called_once_with(length=5, label="Indexing stuff", show_eta=True, show_percent=True)


def test_maybe_progress_true_none_count_show_percent_false() -> None:
    mock_bar = MagicMock()
    mock_progressbar_ctx = MagicMock()
    mock_progressbar_ctx.__enter__ = MagicMock(return_value=mock_bar)
    mock_progressbar_ctx.__exit__ = MagicMock(return_value=False)

    with patch("typer.progressbar", return_value=mock_progressbar_ctx) as mock_pb:
        with _maybe_progress(True, total_count=None, label="Indexing") as progress:
            assert progress is mock_bar

        _, kwargs = mock_pb.call_args
        assert kwargs["show_percent"] is False


# ---------------------------------------------------------------------------
# Indexer.run
# ---------------------------------------------------------------------------


def test_run_empty_entities_returns_zero(mock_config: MagicMock) -> None:
    idx = _make_indexer(mock_config)
    with patch.object(idx, "_process_chunk", return_value=(0, 0)) as mock_proc:
        result = idx.run([])
    assert result == 0
    mock_proc.assert_not_called()


def test_run_single_entity_processes_once(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    idx = _make_indexer(mock_config, chunk_size=10)
    with patch.object(idx, "_process_chunk", return_value=(3, 0)) as mock_proc:
        result = idx.run([mock_entity])
    assert result == 3
    mock_proc.assert_called_once()


def test_run_chunk_boundary_flushes_correctly(mock_config: MagicMock) -> None:
    """3 entities with chunk_size=2 -> 2 flush calls (one at boundary, one for remainder)."""
    idx = _make_indexer(mock_config, chunk_size=2)
    entities = [MagicMock() for _ in range(3)]
    entities[0].subscription_id = UUID("00000000-0000-0000-0000-000000000001")
    entities[1].subscription_id = UUID("00000000-0000-0000-0000-000000000002")
    entities[2].subscription_id = UUID("00000000-0000-0000-0000-000000000003")

    chunk_sizes: list[int] = []

    def _tracking_process_chunk(chunk, session=None):
        chunk_sizes.append(len(chunk))
        return (len(chunk), 0)

    with patch.object(idx, "_process_chunk", side_effect=_tracking_process_chunk):
        result = idx.run(entities)

    assert chunk_sizes == [2, 1]
    assert result == 3


def test_run_progress_updated_on_full_chunk(mock_config: MagicMock) -> None:
    """When a full chunk is flushed, progress.update is called with chunk_size."""
    idx = _make_indexer(mock_config, chunk_size=2)
    idx.show_progress = True
    idx.total_count = 3

    entities = [MagicMock() for _ in range(3)]
    for i, e in enumerate(entities):
        e.subscription_id = UUID(f"00000000-0000-0000-0000-{i:012d}")

    mock_progress = MagicMock()

    @contextmanager
    def _fake_progress(*args, **kwargs):
        yield mock_progress

    with (
        patch.object(idx, "_process_chunk", side_effect=lambda chunk, session=None: (len(chunk), 0)),
        patch("orchestrator.core.search.indexing.indexer._maybe_progress", side_effect=_fake_progress),
    ):
        idx.run(entities)

    mock_progress.update.assert_any_call(2)
    assert mock_progress.update.call_count == 2


def test_run_progress_none_does_not_update(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """When show_progress=False progress is None and update is not called."""
    idx = _make_indexer(mock_config)
    with patch.object(idx, "_process_chunk", return_value=(1, 0)):
        idx.run([mock_entity])
    # No AttributeError - confirms progress was None throughout


def test_run_dry_run_uses_nullcontext(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """dry_run=True should use nullcontext (no db.database_scope call)."""
    idx = _make_indexer(mock_config, dry_run=True)
    with (
        patch("orchestrator.core.search.indexing.indexer.db") as mock_db,
        patch.object(idx, "_process_chunk", return_value=(1, 0)),
    ):
        idx.run([mock_entity])
    mock_db.database_scope.assert_not_called()


def test_run_non_dry_run_uses_database_scope(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """dry_run=False should call db.database_scope()."""
    idx = _make_indexer(mock_config, dry_run=False)

    mock_database = MagicMock()
    mock_database.session = MagicMock()

    @contextmanager
    def _fake_scope():
        yield mock_database

    with (
        patch("orchestrator.core.search.indexing.indexer.db") as mock_db,
        patch.object(idx, "_process_chunk", return_value=(1, 0)),
    ):
        mock_db.database_scope.return_value = _fake_scope()
        idx.run([mock_entity])

    mock_db.database_scope.assert_called_once()


def test_run_returns_total_processed_count(mock_config: MagicMock) -> None:
    """run() aggregates processed counts across all chunks."""
    idx = _make_indexer(mock_config, chunk_size=2)
    entities = [MagicMock() for _ in range(4)]
    for i, e in enumerate(entities):
        e.subscription_id = UUID(f"00000000-0000-0000-0000-{i:012d}")

    with patch.object(idx, "_process_chunk", return_value=(3, 1)):
        result = idx.run(entities)

    assert result == 6  # 2 chunks x 3 processed each


# ---------------------------------------------------------------------------
# Indexer._process_chunk
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "session",
    [
        pytest.param(None, id="no_session"),
        pytest.param(MagicMock(), id="with_session"),
    ],
)
def test_process_chunk_empty_returns_zero_zero(indexer: Indexer, session) -> None:
    result = indexer._process_chunk([], session=session)
    assert result == (0, 0)


def test_process_chunk_with_fields_executes_batches(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """Non-dry-run with fields: session.execute should be called per batch."""
    idx = Indexer(config=mock_config, dry_run=False, force_index=True, chunk_size=10)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE

    mock_session = MagicMock()
    fake_record: IndexableRecord = {
        "entity_id": ENTITY_ID,
        "entity_type": EntityType.SUBSCRIPTION.value,
        "entity_title": ENTITY_TITLE,
        "path": Ltree("root.description"),
        "value": "Hello",
        "value_type": FieldType.STRING,
        "content_hash": "abc",
        "embedding_hash": None,
    }

    with (
        patch.object(idx, "_determine_changes", return_value=([("eid", MagicMock())], [], 0)),
        patch.object(idx, "_generate_upsert_batches", return_value=iter([IndexBatch([fake_record], [])])),
    ):
        processed, identical = idx._process_chunk([mock_entity], session=mock_session)

    mock_session.execute.assert_called_once()
    assert processed == 1
    assert identical == 0


_API = "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch"


def _embedding(embedding_hash: str) -> EmbeddingRecord:
    return EmbeddingRecord(entity_type="SUBSCRIPTION", embedding_hash=embedding_hash, embedding=[0.1])


def _hash_of(entity_id: str) -> str:
    return compute_embedding_hash(EMBEDDING_MODEL, f"root.{entity_id}: v")


def _statements(session: MagicMock) -> list[tuple[str, list]]:
    return [(call.args[0].table.name, call.args[1]) for call in session.execute.call_args_list]


def test_process_chunk_collects_the_chunk_before_writing(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """Every batch is built (embedding included) before the first write, so no lock is held across an API call."""
    idx = Indexer(config=mock_config, dry_run=False, force_index=True, chunk_size=10)
    mock_session = MagicMock()
    first, second = _record("a", "a-hash"), _record("b", "b-hash")
    built: list[int] = []

    def batches():
        built.append(1)
        yield IndexBatch([first], [_embedding("a-hash")])
        built.append(1)
        yield IndexBatch([second], [_embedding("b-hash")])

    def execute(*args):
        assert len(built) == 2  # both batches existed before the first write

    mock_session.execute.side_effect = execute

    with (
        patch.object(idx, "_determine_changes", return_value=([("eid", MagicMock())], [], 0)),
        patch.object(idx, "_generate_upsert_batches", side_effect=lambda *args: batches()),
        patch.object(idx, "_existing_embedding_hashes", return_value=set()),
    ):
        idx._process_chunk([mock_entity], session=mock_session)

    assert mock_session.execute.call_count == 3


def test_write_batches_inserts_the_vectors_of_all_batches_in_one_sorted_statement(indexer: Indexer) -> None:
    """Batches in field order must not decide the lock order: one statement, sorted by hash, then the rows."""
    mock_session = MagicMock()
    first, second = _record("a", "z"), _record("b", "a")
    indexer.dry_run = False

    with patch.object(indexer, "_existing_embedding_hashes", return_value=set()):
        indexer._write_batches(
            [IndexBatch([first], [_embedding("z")]), IndexBatch([second], [_embedding("a")])], mock_session
        )

    statements = _statements(mock_session)
    assert [name for name, _ in statements] == ["ai_search_embeddings", "ai_search_index", "ai_search_index"]
    assert [row["embedding_hash"] for row in statements[0][1]] == ["a", "z"]
    assert [rows for _, rows in statements[1:]] == [[first], [second]]


def _conflict_clause(statement) -> str:
    sql = str(statement.compile(dialect=postgresql.dialect()))
    return sql[sql.index("ON CONFLICT") :]


def test_embedding_insert_statement_keeps_the_stored_vector_by_default() -> None:
    assert _conflict_clause(Indexer._get_embedding_insert_statement()) == "ON CONFLICT DO NOTHING"


def test_embedding_insert_statement_replaces_the_stored_vector_with_replace() -> None:
    clause = _conflict_clause(Indexer._get_embedding_insert_statement(replace=True))

    assert clause == "ON CONFLICT (entity_type, embedding_hash) DO UPDATE SET embedding = excluded.embedding"


@pytest.mark.parametrize("force_index", [False, True], ids=["no_force", "force_index"])
def test_write_batches_picks_the_insert_statement_by_force_index(indexer: Indexer, force_index: bool) -> None:
    mock_session = MagicMock()
    indexer.dry_run = False
    indexer.force_index = force_index

    with patch.object(indexer, "_existing_embedding_hashes", return_value=set()):
        indexer._write_batches([IndexBatch([_record("a", "h")], [_embedding("h")])], mock_session)

    clause = _conflict_clause(mock_session.execute.call_args_list[0].args[0])
    assert clause.endswith("DO UPDATE SET embedding = excluded.embedding") is force_index


def test_write_batches_without_vectors_writes_only_the_rows(indexer: Indexer) -> None:
    mock_session = MagicMock()
    record = _record("a", None)
    indexer.dry_run = False

    indexer._write_batches([IndexBatch([record], [])], mock_session)

    assert _statements(mock_session) == [("ai_search_index", [record])]


@pytest.mark.parametrize("session", [None, MagicMock()], ids=["no_session", "with_session"])
def test_write_batches_dry_run_executes_nothing(indexer: Indexer, session) -> None:
    with patch(_API) as api:
        indexer._write_batches([IndexBatch([_record("a", "h")], [_embedding("h")])], session)

    api.assert_not_called()
    if session:
        session.execute.assert_not_called()


def test_write_batches_without_session_writes_nothing(indexer: Indexer) -> None:
    indexer.dry_run = False

    indexer._write_batches([IndexBatch([_record("a", "h")], [])], None)


def test_write_batches_drops_the_hash_of_a_text_that_failed_in_the_batch(indexer: Indexer) -> None:
    mock_session = MagicMock()
    record = _record("a", "h")
    indexer.dry_run = False
    indexer._failed_embedding_hashes.add("h")

    indexer._write_batches([IndexBatch([record], [])], mock_session)

    assert _statements(mock_session) == [("ai_search_index", [{**record, "embedding_hash": None}])]


def test_process_chunk_dry_run_does_not_execute(indexer: Indexer, mock_entity: MagicMock) -> None:
    """dry_run=True: batches are logged, session.execute is never called."""
    mock_session = MagicMock()
    fake_record: IndexableRecord = {
        "entity_id": ENTITY_ID,
        "entity_type": EntityType.SUBSCRIPTION.value,
        "entity_title": ENTITY_TITLE,
        "path": Ltree("root.description"),
        "value": "Hello",
        "value_type": FieldType.STRING,
        "content_hash": "abc",
        "embedding_hash": None,
    }

    with (
        patch.object(indexer, "_determine_changes", return_value=([("eid", MagicMock())], [], 0)),
        patch.object(indexer, "_generate_upsert_batches", return_value=iter([IndexBatch([fake_record], [])])),
    ):
        processed, identical = indexer._process_chunk([mock_entity], session=mock_session)

    mock_session.execute.assert_not_called()
    assert processed == 1


def test_process_chunk_paths_to_delete_without_session_skips(indexer: Indexer, mock_entity: MagicMock) -> None:
    """If paths_to_delete is non-empty but session is None, _execute_batched_deletes is NOT called."""
    with (
        patch.object(
            indexer,
            "_determine_changes",
            return_value=([], [(ENTITY_ID, Ltree("root.old_path"))], 0),
        ),
        patch.object(indexer, "_execute_batched_deletes") as mock_deletes,
    ):
        indexer._process_chunk([mock_entity], session=None)

    mock_deletes.assert_not_called()


def test_process_chunk_paths_to_delete_with_session_calls_deletes(
    mock_config: MagicMock, mock_entity: MagicMock
) -> None:
    """If paths_to_delete is non-empty and session is provided, _execute_batched_deletes is called."""
    idx = Indexer(config=mock_config, dry_run=False, force_index=False, chunk_size=10)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE

    mock_session = MagicMock()
    paths = [(ENTITY_ID, Ltree("root.old_path"))]

    with (
        patch.object(idx, "_determine_changes", return_value=([], paths, 0)),
        patch.object(idx, "_execute_batched_deletes") as mock_deletes,
    ):
        idx._process_chunk([mock_entity], session=mock_session)

    mock_deletes.assert_called_once_with(paths, mock_session)


# ---------------------------------------------------------------------------
# Indexer._execute_batched_deletes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("num_paths", "chunk_size", "expected_execute_calls"),
    [
        pytest.param(5, 10, 1, id="all_in_one_batch"),
        pytest.param(5, 2, 3, id="multiple_batches_2_2_1"),
        pytest.param(1, 10, 1, id="single_path"),
    ],
)
def test_execute_batched_deletes(indexer: Indexer, num_paths, chunk_size, expected_execute_calls) -> None:
    mock_session = MagicMock()
    paths = [(ENTITY_ID, Ltree(f"root.path{i}")) for i in range(num_paths)]
    indexer.chunk_size = chunk_size

    indexer._execute_batched_deletes(paths, mock_session)

    assert mock_session.execute.call_count == expected_execute_calls


# ---------------------------------------------------------------------------
# Indexer._get_all_existing_hashes
# ---------------------------------------------------------------------------


def test_get_all_existing_hashes_empty_ids(indexer: Indexer) -> None:
    mock_session = MagicMock()
    result = indexer._get_all_existing_hashes([], mock_session)
    assert result == {}
    mock_session.execute.assert_not_called()


_ENTITY_ID_1 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_ENTITY_ID_2 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

_HASH_DB_ROWS = [
    (_ENTITY_ID_1, "root.name", "hash_name_1", "emb_name_1"),
    (_ENTITY_ID_1, "root.status", "hash_status_1", None),
    (_ENTITY_ID_2, "root.name", "hash_name_2", "emb_name_2"),
]


def test_get_all_existing_hashes_returns_dict_of_dicts(indexer: Indexer) -> None:
    mock_session = MagicMock()
    mock_session.execute.return_value.all.return_value = _HASH_DB_ROWS

    result = indexer._get_all_existing_hashes([_ENTITY_ID_1, _ENTITY_ID_2], mock_session)

    assert set(result.keys()) == {_ENTITY_ID_1, _ENTITY_ID_2}
    assert result[_ENTITY_ID_1] == {
        "root.name": StoredHashes("hash_name_1", "emb_name_1"),
        "root.status": StoredHashes("hash_status_1", None),
    }
    assert result[_ENTITY_ID_2] == {"root.name": StoredHashes("hash_name_2", "emb_name_2")}


def test_get_all_existing_hashes_no_rows_gets_empty_inner_dict(indexer: Indexer) -> None:
    mock_session = MagicMock()
    entity_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    mock_session.execute.return_value.all.return_value = []

    result = indexer._get_all_existing_hashes([entity_id], mock_session)

    assert result == {entity_id: {}}


def test_get_all_existing_hashes_path_values_are_stringified(indexer: Indexer) -> None:
    """Paths and entity_ids must be cast to str when building the result dict."""
    mock_session = MagicMock()
    ltree_path = Ltree("root.description")

    mock_session.execute.return_value.all.return_value = [
        (ENTITY_ID, ltree_path, "hash123", "emb123"),
    ]

    result = indexer._get_all_existing_hashes([ENTITY_ID], mock_session)

    assert str(ltree_path) in result[ENTITY_ID]
    assert result[ENTITY_ID][str(ltree_path)] == StoredHashes("hash123", "emb123")


# ---------------------------------------------------------------------------
# Indexer._generate_upsert_batches
# ---------------------------------------------------------------------------


def test_upsert_non_embeddable_field_accumulated_directly(indexer: Indexer) -> None:
    field = _non_embeddable_field()
    fields = [(ENTITY_ID, field)]

    with (
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
        patch("litellm.utils.get_max_tokens", return_value=100),
    ):
        mock_llm.EMBEDDING_SAFE_MARGIN_PERCENT = 0.1
        mock_llm.EMBEDDING_MAX_BATCH_SIZE = None
        batches = list(indexer._generate_upsert_batches(fields))

    assert len(batches) == 1
    assert len(batches[0].records) == 1
    assert batches[0].records[0]["embedding_hash"] is None
    assert batches[0].embeddings == []


def test_upsert_embeddable_field_with_embedding(indexer: Indexer) -> None:
    field = _embeddable_field()
    fields = [(ENTITY_ID, field)]

    with (
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
        patch("litellm.utils.get_max_tokens", return_value=100),
        patch("litellm.utils.encode", return_value=[1, 2, 3]),
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            return_value=[[0.1, 0.2]],
        ),
    ):
        mock_llm.EMBEDDING_SAFE_MARGIN_PERCENT = 0.1
        mock_llm.EMBEDDING_MAX_BATCH_SIZE = None
        batches = list(indexer._generate_upsert_batches(fields))

    assert len(batches) == 1
    assert batches[0].records[0]["embedding_hash"] == batches[0].embeddings[0]["embedding_hash"]
    assert batches[0].embeddings[0]["embedding"] == [0.1, 0.2]
    assert batches[0].embeddings[0]["entity_type"] == EntityType.SUBSCRIPTION.value


_TOKEN_BUDGET_FIELD_1 = _embeddable_field("root.desc", "First text")
_TOKEN_BUDGET_FIELD_2 = _embeddable_field("root.title", "Second text")


_TOKEN_BUDGET_FIELDS = [(ENTITY_ID, _TOKEN_BUDGET_FIELD_1), (ENTITY_ID, _TOKEN_BUDGET_FIELD_2)]


def test_upsert_token_budget_exceeded_flushes_before_adding(indexer: Indexer) -> None:
    """Two embeddable fields where second exceeds the token budget -> two separate batches."""

    def mock_encode(model, text):
        return [1] * 50  # 50 tokens each; budget = 100 * (1 - 0.1) = 90, so second overflows

    with (
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
        patch("litellm.utils.get_max_tokens", return_value=100),
        patch("litellm.utils.encode", side_effect=mock_encode),
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            side_effect=[[[0.1]], [[0.2]]],
        ),
    ):
        mock_llm.EMBEDDING_SAFE_MARGIN_PERCENT = 0.1  # budget = 90; 50+50 > 90 -> flush
        mock_llm.EMBEDDING_MAX_BATCH_SIZE = None
        batches = list(indexer._generate_upsert_batches(_TOKEN_BUDGET_FIELDS))

    assert len(batches) == 2


def test_upsert_max_batch_size_triggers_flush(indexer: Indexer) -> None:
    """Reaching max_batch_size limit causes a flush even when token budget is not exceeded."""
    fields = [(ENTITY_ID, _embeddable_field(f"root.f{i}", "x")) for i in range(3)]

    with (
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
        patch("litellm.utils.get_max_tokens", return_value=10000),
        patch("litellm.utils.encode", return_value=[1]),  # 1 token each
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            side_effect=[[[0.1], [0.2]], [[0.3]]],
        ),
    ):
        mock_llm.EMBEDDING_SAFE_MARGIN_PERCENT = 0.0
        mock_llm.EMBEDDING_MAX_BATCH_SIZE = 2  # flush every 2 embeddable items
        batches = list(indexer._generate_upsert_batches(fields))

    assert len(batches) == 2


def test_upsert_field_exceeds_max_context_is_skipped(indexer: Indexer) -> None:
    field = _embeddable_field("root.huge", "lots of text")
    fields = [(ENTITY_ID, field)]

    with (
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
        patch("litellm.utils.get_max_tokens", return_value=100),
        patch("litellm.utils.encode", return_value=[1] * 200),  # > max_ctx=100
    ):
        mock_llm.EMBEDDING_SAFE_MARGIN_PERCENT = 0.0
        mock_llm.EMBEDDING_MAX_BATCH_SIZE = None
        batches = list(indexer._generate_upsert_batches(fields))

    assert batches == []


def test_upsert_tokenization_failure_skips_field(indexer: Indexer) -> None:
    field = _embeddable_field()
    fields = [(ENTITY_ID, field)]

    with (
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
        patch("litellm.utils.get_max_tokens", return_value=100),
        patch("litellm.utils.encode", side_effect=Exception("tokenizer broken")),
    ):
        mock_llm.EMBEDDING_SAFE_MARGIN_PERCENT = 0.0
        mock_llm.EMBEDDING_MAX_BATCH_SIZE = None
        batches = list(indexer._generate_upsert_batches(fields))

    assert batches == []


_MIXED_FIELDS = [
    (ENTITY_ID, _embeddable_field("root.desc", "Hello world")),
    (ENTITY_ID, _non_embeddable_field("root.insync", "true")),
]


def test_upsert_mixed_embeddable_and_non_embeddable(indexer: Indexer) -> None:
    with (
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
        patch("litellm.utils.get_max_tokens", return_value=100),
        patch("litellm.utils.encode", return_value=[1, 2]),
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            return_value=[[0.5]],
        ),
    ):
        mock_llm.EMBEDDING_SAFE_MARGIN_PERCENT = 0.0
        mock_llm.EMBEDDING_MAX_BATCH_SIZE = None
        batches = list(indexer._generate_upsert_batches(_MIXED_FIELDS))

    assert len(batches) == 1
    assert len(batches[0].records) == 2
    assert len(batches[0].embeddings) == 1


def test_upsert_failed_text_is_not_retried_in_a_later_chunk(indexer: Indexer) -> None:
    """An outage sends a repeated text once per run, not once per chunk, while its records are still written."""
    repeated = _embeddable_field("root.description", "Same text for every entity")
    chunks = [[(ENTITY_ID, repeated)], [(ENTITY_ID, repeated)]]

    with (
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
        patch("litellm.utils.get_max_tokens", return_value=100),
        patch("litellm.utils.encode", return_value=[1, 2]),
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            return_value=[[]],
        ) as mock_embed,
    ):
        mock_llm.EMBEDDING_SAFE_MARGIN_PERCENT = 0.0
        mock_llm.EMBEDDING_MAX_BATCH_SIZE = None
        batches = [batch for chunk in chunks for batch in indexer._generate_upsert_batches(chunk)]

    assert mock_embed.call_count == 1
    assert [len(batch.records) for batch in batches] == [1, 1]
    assert all(batch.embeddings == [] for batch in batches)


@pytest.mark.parametrize(
    ("force_index", "dry_run", "api_enabled", "handled", "lookups"),
    [
        pytest.param(False, False, True, True, 1, id="stored_vector_is_handled"),
        pytest.param(False, False, False, True, 1, id="stored_vector_is_handled_with_the_api_disabled"),
        pytest.param(True, False, True, False, 0, id="force_index_handles_nothing"),
        pytest.param(False, True, True, False, 0, id="dry_run_handles_nothing"),
    ],
)
def test_determine_changes_marks_the_stored_vectors_as_handled(
    mock_config: MagicMock,
    mock_entity: MagicMock,
    force_index: bool,
    dry_run: bool,
    api_enabled: bool,
    handled: bool,
    lookups: int,
) -> None:
    """One lookup per chunk serves change detection and the batches, so nothing is passed between them."""
    idx = Indexer(config=mock_config, dry_run=dry_run, force_index=force_index, chunk_size=10)
    stored = {idx._embedding_hash(field) for field in mock_config.traverser.get_fields.return_value}

    with (
        patch("orchestrator.core.search.indexing.indexer.llm_settings.EMBEDDING_API_ENABLED", api_enabled),
        patch.object(idx, "_get_all_existing_hashes", return_value={}),
        patch.object(idx, "_existing_embedding_hashes", return_value=stored) as lookup,
    ):
        idx._determine_changes([mock_entity], session=MagicMock())

    assert lookup.call_count == lookups
    assert (idx._handled_embedding_hashes == stored) is handled
    assert handled or idx._handled_embedding_hashes == set()


def test_stored_vector_costs_no_api_call_and_force_index_embeds_it_again(
    mock_config: MagicMock, mock_entity: MagicMock
) -> None:
    field = ExtractedField(path="root.a", value="v", value_type=FieldType.STRING)
    mock_config.traverser.get_fields.return_value = [field]
    texts_sent: list[list[str]] = []

    for force_index in (False, True):
        idx = Indexer(config=mock_config, dry_run=False, force_index=force_index, chunk_size=10)
        stored = {idx._embedding_hash(field)}
        with (
            patch("litellm.utils.get_max_tokens", return_value=100),
            patch("litellm.utils.encode", return_value=[1]),
            patch.object(idx, "_get_all_existing_hashes", return_value={}),
            patch.object(idx, "_existing_embedding_hashes", return_value=stored),
            patch.object(idx, "_write_batches"),
            patch(_API, side_effect=lambda texts, dry_run: [[0.1] for _ in texts]) as api,
        ):
            idx._process_chunk([mock_entity], session=MagicMock())
        texts_sent.append([text for call in api.call_args_list for text in call.args[0]])

    assert texts_sent == [[], ["root.a: v"]]


def test_upsert_failed_text_is_retried_on_the_next_run(indexer: Indexer) -> None:
    """The attempted texts of a run do not carry over, so the next run sends the text again."""
    field = _embeddable_field()

    def failing_then_working_api(texts: list[str], dry_run: bool) -> list[list[float]]:
        return [[]] if mock_embed.call_count == 1 else [[0.1, 0.2]]

    with (
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
        patch("litellm.utils.get_max_tokens", return_value=100),
        patch("litellm.utils.encode", return_value=[1, 2]),
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            side_effect=failing_then_working_api,
        ) as mock_embed,
    ):
        mock_llm.EMBEDDING_SAFE_MARGIN_PERCENT = 0.0
        mock_llm.EMBEDDING_MAX_BATCH_SIZE = None
        assert list(indexer._generate_upsert_batches([(ENTITY_ID, field)]))[0].embeddings == []
        assert mock_embed.call_count == 1

        # What run() does at the start of a new run.
        indexer._handled_embedding_hashes = set()
        batches = list(indexer._generate_upsert_batches([(ENTITY_ID, field)]))

    assert mock_embed.call_count == 2
    assert len(batches[0].embeddings) == 1


# ---------------------------------------------------------------------------
# Indexer._flush_buffer
# ---------------------------------------------------------------------------


def test_flush_buffer_without_pending_texts_returns_records_and_skips_the_api(indexer: Indexer) -> None:
    non_emb_record: IndexableRecord = {
        "entity_id": ENTITY_ID,
        "entity_type": EntityType.SUBSCRIPTION.value,
        "entity_title": ENTITY_TITLE,
        "path": Ltree("root.insync"),
        "value": "true",
        "value_type": FieldType.BOOLEAN,
        "content_hash": "somehash",
        "embedding_hash": None,
    }
    with patch("orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch") as mock_embed:
        result = indexer._flush_buffer({}, [non_emb_record])

    mock_embed.assert_not_called()
    assert result == IndexBatch([non_emb_record], [])


def test_flush_buffer_empty_both_returns_empty(indexer: Indexer) -> None:
    assert indexer._flush_buffer({}, []) == IndexBatch([], [])


def test_flush_buffer_embeds_pending_texts_by_hash(indexer: Indexer) -> None:
    with patch(
        "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
        return_value=[[0.1, 0.2], [0.3, 0.4]],
    ) as mock_embed:
        result = indexer._flush_buffer({"h1": "root.a: text a", "h2": "root.b: text b"}, [])

    mock_embed.assert_called_once_with(["root.a: text a", "root.b: text b"], True)
    assert result.embeddings == [
        {"entity_type": "SUBSCRIPTION", "embedding_hash": "h1", "embedding": [0.1, 0.2]},
        {"entity_type": "SUBSCRIPTION", "embedding_hash": "h2", "embedding": [0.3, 0.4]},
    ]


def test_flush_buffer_keeps_records_and_skips_empty_vectors(indexer: Indexer) -> None:
    """A failed text keeps its index record, and gets no embeddings row so that the next run retries it."""
    record = indexer._make_indexable_record(_embeddable_field("root.a", "text a"), ENTITY_ID, "h1")

    with patch(
        "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
        return_value=[[], [0.3]],
    ):
        result = indexer._flush_buffer({"h1": "root.a: text a", "h2": "root.b: text b"}, [record])

    assert result.records == [record]
    assert [e["embedding_hash"] for e in result.embeddings] == ["h2"]
    assert indexer._failed_embedding_hashes == {"h1"}


_MISMATCH_PENDING = {"h1": "root.a: text a", "h2": "root.b: text b"}


def test_flush_buffer_embedding_count_mismatch_raises(indexer: Indexer) -> None:
    with (
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            return_value=[[0.1]],  # only 1 embedding for 2 items
        ),
        pytest.raises(ValueError, match="Embedding mismatch"),
    ):
        indexer._flush_buffer(_MISMATCH_PENDING, [])


def test_flush_buffer_dry_run_embeddings_are_empty(mock_config: MagicMock) -> None:
    """EmbeddingIndexer returns [] per text in dry_run, which must not count as a mismatch."""
    idx = Indexer(config=mock_config, dry_run=True, force_index=False, chunk_size=10)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE
    record = idx._make_indexable_record(_embeddable_field(), ENTITY_ID, "h1")

    with patch(
        "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
        return_value=[[]],
    ):
        result = idx._flush_buffer({"h1": "root.description: Hello world"}, [record])

    assert result == IndexBatch([record], [])


# ---------------------------------------------------------------------------
# Indexer._get_max_tokens
# ---------------------------------------------------------------------------


def test_get_max_tokens_returns_int_from_litellm(indexer: Indexer) -> None:
    with patch("litellm.utils.get_max_tokens", return_value=8191):
        assert indexer._get_max_tokens() == 8191


@pytest.mark.parametrize(
    ("get_max_tokens_rv", "get_max_tokens_se", "fallback", "expected"),
    [
        pytest.param("not-an-int", None, 4096, 4096, id="non_int_return"),
        pytest.param(None, None, 2048, 2048, id="none_return"),
        pytest.param(None, Exception("unknown model"), 512, 512, id="exception_raised"),
    ],
)
def test_get_max_tokens_litellm_invalid_falls_back(
    indexer: Indexer, get_max_tokens_rv, get_max_tokens_se, fallback: int, expected: int
) -> None:
    kwargs = {"side_effect": get_max_tokens_se} if get_max_tokens_se else {"return_value": get_max_tokens_rv}
    with (
        patch("litellm.utils.get_max_tokens", **kwargs),
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
    ):
        mock_llm.EMBEDDING_FALLBACK_MAX_TOKENS = fallback
        mock_llm.EMBEDDING_MODEL = EMBEDDING_MODEL
        result = indexer._get_max_tokens()

    assert result == expected


def test_get_max_tokens_fallback_not_set_raises(indexer: Indexer) -> None:
    with (
        patch("litellm.utils.get_max_tokens", side_effect=Exception("unknown")),
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
    ):
        mock_llm.EMBEDDING_FALLBACK_MAX_TOKENS = None
        mock_llm.EMBEDDING_MODEL = EMBEDDING_MODEL
        with pytest.raises(RuntimeError, match="EMBEDDING_FALLBACK_MAX_TOKENS"):
            indexer._get_max_tokens()


# ---------------------------------------------------------------------------
# Indexer._compute_content_hash (static)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "value", "value_type", "entity_title"),
    [
        pytest.param("root.name", "Alice", FieldType.STRING, "Title A", id="string"),
        pytest.param("root.status", "active", FieldType.STRING, "", id="empty_title"),
        pytest.param("root.count", "42", FieldType.INTEGER, "Entity", id="integer"),
    ],
)
def test_content_hash_is_deterministic(path: str, value: str, value_type: FieldType, entity_title: str) -> None:
    h1 = Indexer._compute_content_hash(path, value, value_type, entity_title)
    h2 = Indexer._compute_content_hash(path, value, value_type, entity_title)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


def test_content_hash_none_value_uses_empty_string() -> None:
    h_none = Indexer._compute_content_hash("p", None, FieldType.STRING, "t")
    h_empty = Indexer._compute_content_hash("p", "", FieldType.STRING, "t")
    assert h_none == h_empty


@pytest.mark.parametrize(
    ("path1", "value1", "path2", "value2", "same"),
    [
        pytest.param("p", "v", "p", "v", True, id="identical"),
        pytest.param("p", "v1", "p", "v2", False, id="different_values"),
        pytest.param("p1", "v", "p2", "v", False, id="different_paths"),
    ],
)
def test_content_hash_sensitivity(path1: str, value1: str, path2: str, value2: str, same: bool) -> None:
    h1 = Indexer._compute_content_hash(path1, value1, FieldType.STRING, "t")
    h2 = Indexer._compute_content_hash(path2, value2, FieldType.STRING, "t")
    assert (h1 == h2) is same


def test_content_hash_different_entity_title() -> None:
    h1 = Indexer._compute_content_hash("p", "v", FieldType.STRING, "Title A")
    h2 = Indexer._compute_content_hash("p", "v", FieldType.STRING, "Title B")
    assert h1 != h2


# ---------------------------------------------------------------------------
# Indexer._make_indexable_record
# ---------------------------------------------------------------------------


def test_make_indexable_record_fields_populated(indexer: Indexer) -> None:
    field = ExtractedField(path="root.description", value="Hello", value_type=FieldType.STRING)

    record = indexer._make_indexable_record(field, ENTITY_ID, "some-hash")

    assert record["entity_id"] == ENTITY_ID
    assert record["entity_type"] == EntityType.SUBSCRIPTION.value
    assert record["entity_title"] == ENTITY_TITLE
    assert record["path"] == Ltree("root.description")
    assert record["value"] == "Hello"
    assert record["value_type"] == FieldType.STRING
    assert isinstance(record["content_hash"], str)
    assert len(record["content_hash"]) == 64
    assert record["embedding_hash"] == "some-hash"
    assert "embedding" not in record


def test_make_indexable_record_path_wrapped_in_ltree(indexer: Indexer) -> None:
    field = ExtractedField(path="root.some.nested.path", value="val", value_type=FieldType.STRING)
    record = indexer._make_indexable_record(field, ENTITY_ID, None)
    assert isinstance(record["path"], Ltree)
    assert str(record["path"]) == "root.some.nested.path"


def test_make_indexable_record_hash_matches_compute(indexer: Indexer) -> None:
    field = ExtractedField(path="root.description", value="Some value", value_type=FieldType.STRING)
    record = indexer._make_indexable_record(field, ENTITY_ID, None)
    expected_hash = Indexer._compute_content_hash(field.path, field.value, field.value_type, ENTITY_TITLE)
    assert record["content_hash"] == expected_hash


# ---------------------------------------------------------------------------
# Embedding deduplication
# ---------------------------------------------------------------------------

_OTHER_ENTITY_IDS = [f"00000000-0000-0000-0000-00000000000{i}" for i in range(1, 6)]


@contextmanager
def _embedding_api():
    """Stub litellm and the embedding API, which answers one vector per text."""
    with (
        patch("litellm.utils.get_max_tokens", return_value=8191),
        patch("litellm.utils.encode", return_value=[1, 2]),
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            side_effect=lambda texts, dry_run: [[0.1] for _ in texts],
        ) as api,
    ):
        yield api


def _indexer_with_titles(mock_config: MagicMock, entity_ids: list[str]) -> Indexer:
    idx = _make_indexer(mock_config, dry_run=False)
    idx._entity_titles.update(dict.fromkeys(entity_ids, ENTITY_TITLE))
    return idx


def test_identical_texts_embedded_once(mock_config: MagicMock) -> None:
    idx = _indexer_with_titles(mock_config, _OTHER_ENTITY_IDS)
    fields = [(entity_id, _embeddable_field("root.tag", "noc")) for entity_id in _OTHER_ENTITY_IDS]

    with _embedding_api() as api:
        batches = list(idx._generate_upsert_batches(fields))

    api.assert_called_once()
    assert api.call_args.args[0] == ["root.tag: noc"]
    assert len(batches) == 1
    assert len(batches[0].embeddings) == 1
    assert {record["embedding_hash"] for record in batches[0].records} == {batches[0].embeddings[0]["embedding_hash"]}
    assert len(batches[0].records) == 5


@pytest.mark.parametrize(
    ("values", "distinct_texts"),
    [
        pytest.param(["NOC", "noc"], 1, id="case_differs"),
        pytest.param(["NOC", "Noc", "noc", "nOC"], 1, id="mixed_case"),
        pytest.param(["noc", "noc2"], 2, id="different_text"),
    ],
)
def test_case_insensitive_dedupe(mock_config: MagicMock, values: list[str], distinct_texts: int) -> None:
    idx = _indexer_with_titles(mock_config, _OTHER_ENTITY_IDS)
    fields = [(entity_id, _embeddable_field("root.tag", value)) for entity_id, value in zip(_OTHER_ENTITY_IDS, values)]

    with _embedding_api() as api:
        batches = list(idx._generate_upsert_batches(fields))

    assert len(api.call_args.args[0]) == distinct_texts
    assert len(batches[0].embeddings) == distinct_texts
    assert len(batches[0].records) == len(values)


def test_known_hash_not_re_embedded(mock_config: MagicMock) -> None:
    idx = _indexer_with_titles(mock_config, [ENTITY_ID])
    known = _embeddable_field("root.tag", "noc")
    unknown = _embeddable_field("root.tag", "other")
    known_hash = idx._embedding_hash(known)

    idx._handled_embedding_hashes.add(known_hash)

    with _embedding_api() as api:
        batches = list(idx._generate_upsert_batches([(ENTITY_ID, known), (ENTITY_ID, unknown)]))

    assert api.call_args.args[0] == ["root.tag: other"]
    assert [record["embedding_hash"] for record in batches[0].records] == [known_hash, idx._embedding_hash(unknown)]
    assert [e["embedding_hash"] for e in batches[0].embeddings] == [idx._embedding_hash(unknown)]


def test_only_known_hashes_never_calls_the_api(mock_config: MagicMock) -> None:
    idx = _indexer_with_titles(mock_config, [ENTITY_ID])
    field = _embeddable_field("root.tag", "noc")

    idx._handled_embedding_hashes.add(idx._embedding_hash(field))

    with _embedding_api() as api:
        batches = list(idx._generate_upsert_batches([(ENTITY_ID, field)]))

    api.assert_not_called()
    assert batches == [IndexBatch(batches[0].records, [])]
    assert len(batches[0].records) == 1


def test_text_is_not_embedded_again_in_a_later_batch(mock_config: MagicMock) -> None:
    """A text flushed in an earlier batch of the same run counts as handled, or it is sent twice."""
    idx = _indexer_with_titles(mock_config, [ENTITY_ID])
    fields = [
        (ENTITY_ID, _embeddable_field("root.a", "x")),
        (ENTITY_ID, _embeddable_field("root.b", "y")),
        (ENTITY_ID, _embeddable_field("root.a", "x")),
    ]

    with _embedding_api() as api, patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm:
        mock_llm.EMBEDDING_SAFE_MARGIN_PERCENT = 0.0
        mock_llm.EMBEDDING_MAX_BATCH_SIZE = 1
        batches = list(idx._generate_upsert_batches(fields))

    assert [call.args[0] for call in api.call_args_list] == [["root.a: x"], ["root.b: y"]]
    assert [len(batch.records) for batch in batches] == [1, 2]


@pytest.mark.parametrize(
    ("api_enabled", "dry_run", "stored_matches", "vector_stored", "expected_changed"),
    [
        pytest.param(False, False, False, False, 0, id="api_disabled_marks_nothing_changed"),
        pytest.param(True, True, False, False, 0, id="dry_run_marks_nothing_changed"),
        pytest.param(True, False, True, True, 0, id="vector_present"),
        pytest.param(True, False, True, False, 2, id="vector_missing_after_failed_batch"),
        pytest.param(True, False, False, True, 2, id="stored_hash_differs_after_model_switch"),
        pytest.param(True, False, False, False, 2, id="never_embedded"),
    ],
)
def test_determine_changes_embedding_rule(
    mock_config: MagicMock,
    mock_entity: MagicMock,
    mock_fields: list[ExtractedField],
    api_enabled: bool,
    dry_run: bool,
    stored_matches: bool,
    vector_stored: bool,
    expected_changed: int,
) -> None:
    idx = _make_indexer(mock_config, dry_run=dry_run)
    current_hashes = {field.path: idx._embedding_hash(field) for field in mock_fields}
    stored = {
        ENTITY_ID: {
            field.path: StoredHashes(
                Indexer._compute_content_hash(field.path, field.value, field.value_type, ENTITY_TITLE),
                (current_hashes[field.path] if stored_matches else "old-model-hash")
                if field.value_type.is_embeddable(field.value)
                else None,
            )
            for field in mock_fields
        }
    }

    with (
        patch("orchestrator.core.search.indexing.indexer.llm_settings.EMBEDDING_API_ENABLED", api_enabled),
        patch.object(idx, "_get_all_existing_hashes", return_value=stored),
        patch.object(
            idx, "_existing_embedding_hashes", return_value=set(current_hashes.values()) if vector_stored else set()
        ) as lookup,
    ):
        changed, deleted, identical = idx._determine_changes([mock_entity], session=MagicMock())

    assert len(changed) == expected_changed
    assert deleted == []
    assert identical == len(mock_fields) - expected_changed
    assert lookup.called is (not dry_run)


def test_determine_changes_marks_a_changed_title_as_changed_without_the_lookup(
    mock_config: MagicMock, mock_entity: MagicMock, mock_fields: list[ExtractedField]
) -> None:
    """The content hash includes the entity title, so a title change rewrites every row of the entity."""
    idx = _make_indexer(mock_config, dry_run=True)
    stored = {
        ENTITY_ID: {
            field.path: StoredHashes(
                Indexer._compute_content_hash(field.path, field.value, field.value_type, "Old title"), None
            )
            for field in mock_fields
        }
    }

    with patch.object(idx, "_get_all_existing_hashes", return_value=stored):
        changed, _, identical = idx._determine_changes([mock_entity], session=MagicMock())

    assert len(changed) == len(mock_fields)
    assert identical == 0


def test_existing_embedding_hashes_scopes_to_entity_type_and_batches(mock_config: MagicMock) -> None:
    idx = _make_indexer(mock_config, chunk_size=2)
    session = MagicMock()
    session.scalars.side_effect = [["a", "b"], ["c"]]

    found = idx._existing_embedding_hashes({"a", "b", "c", "d"}, session)

    assert found == {"a", "b", "c"}
    assert session.scalars.call_count == 2
    assert "ai_search_embeddings.entity_type" in str(session.scalars.call_args.args[0])
    assert session.scalars.call_args.args[0].compile().params["entity_type_1"] == "SUBSCRIPTION"


def test_existing_embedding_hashes_empty_set_runs_no_query(mock_config: MagicMock) -> None:
    session = MagicMock()
    assert _make_indexer(mock_config)._existing_embedding_hashes(set(), session) == set()
    session.scalars.assert_not_called()


@pytest.mark.parametrize(
    ("model_id", "other_model_id", "same"),
    [
        pytest.param("model-a", "model-a", True, id="same_model"),
        pytest.param("model-a", "model-b", False, id="model_switch"),
    ],
)
def test_embedding_hash_uses_the_model_captured_at_init(
    indexer: Indexer, model_id: str, other_model_id: str, same: bool
) -> None:
    field = _embeddable_field("root.tag", "NOC")
    with patch.object(indexer, "embedding_model", model_id):
        first = indexer._embedding_hash(field)
    with patch.object(indexer, "embedding_model", other_model_id):
        second = indexer._embedding_hash(field)

    assert first == compute_embedding_hash(model_id, "root.tag: NOC")
    assert (first == second) is same
