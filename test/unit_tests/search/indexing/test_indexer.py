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
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.search.core.types import EntityType, ExtractedField, FieldType, IndexableRecord
from orchestrator.core.search.indexing.indexer import Indexer, _maybe_begin, _maybe_progress

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
        "embedding": [0.1],
    }

    with (
        patch.object(idx, "_determine_changes", return_value=([("eid", MagicMock())], [], 0)),
        patch.object(idx, "_generate_upsert_batches", return_value=iter([[fake_record]])),
    ):
        processed, identical = idx._process_chunk([mock_entity], session=mock_session)

    mock_session.execute.assert_called_once()
    assert processed == 1
    assert identical == 0


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
        "embedding": None,
    }

    with (
        patch.object(indexer, "_determine_changes", return_value=([("eid", MagicMock())], [], 0)),
        patch.object(indexer, "_generate_upsert_batches", return_value=iter([[fake_record]])),
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
    mock_session.query.assert_not_called()


_ENTITY_ID_1 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_ENTITY_ID_2 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

_HASH_DB_ROWS = [
    (_ENTITY_ID_1, "root.name", "hash_name_1"),
    (_ENTITY_ID_1, "root.status", "hash_status_1"),
    (_ENTITY_ID_2, "root.name", "hash_name_2"),
]


def test_get_all_existing_hashes_returns_dict_of_dicts(indexer: Indexer) -> None:
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = _HASH_DB_ROWS

    result = indexer._get_all_existing_hashes([_ENTITY_ID_1, _ENTITY_ID_2], mock_session)

    assert set(result.keys()) == {_ENTITY_ID_1, _ENTITY_ID_2}
    assert result[_ENTITY_ID_1] == {"root.name": "hash_name_1", "root.status": "hash_status_1"}
    assert result[_ENTITY_ID_2] == {"root.name": "hash_name_2"}


def test_get_all_existing_hashes_no_rows_gets_empty_inner_dict(indexer: Indexer) -> None:
    mock_session = MagicMock()
    entity_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    mock_session.query.return_value.filter.return_value.all.return_value = []

    result = indexer._get_all_existing_hashes([entity_id], mock_session)

    assert result == {entity_id: {}}


def test_get_all_existing_hashes_path_values_are_stringified(indexer: Indexer) -> None:
    """Paths and entity_ids must be cast to str when building the result dict."""
    mock_session = MagicMock()
    ltree_path = Ltree("root.description")

    mock_session.query.return_value.filter.return_value.all.return_value = [
        (ENTITY_ID, ltree_path, "hash123"),
    ]

    result = indexer._get_all_existing_hashes([ENTITY_ID], mock_session)

    assert str(ltree_path) in result[ENTITY_ID]
    assert result[ENTITY_ID][str(ltree_path)] == "hash123"


# ---------------------------------------------------------------------------
# Indexer._generate_upsert_batches
# ---------------------------------------------------------------------------


def test_upsert_non_embeddable_field_accumulated_directly(indexer: Indexer) -> None:
    field = _non_embeddable_field()
    fields = [(ENTITY_ID, field)]

    with (
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
        patch("orchestrator.core.search.indexing.indexer.get_max_tokens", return_value=100),
    ):
        mock_llm.EMBEDDING_SAFE_MARGIN_PERCENT = 0.1
        mock_llm.EMBEDDING_MAX_BATCH_SIZE = None
        batches = list(indexer._generate_upsert_batches(fields))

    assert len(batches) == 1
    assert len(batches[0]) == 1
    assert batches[0][0]["embedding"] is None


def test_upsert_embeddable_field_with_embedding(indexer: Indexer) -> None:
    field = _embeddable_field()
    fields = [(ENTITY_ID, field)]

    with (
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
        patch("orchestrator.core.search.indexing.indexer.get_max_tokens", return_value=100),
        patch("orchestrator.core.search.indexing.indexer.encode", return_value=[1, 2, 3]),
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            return_value=[[0.1, 0.2]],
        ),
    ):
        mock_llm.EMBEDDING_SAFE_MARGIN_PERCENT = 0.1
        mock_llm.EMBEDDING_MAX_BATCH_SIZE = None
        batches = list(indexer._generate_upsert_batches(fields))

    assert len(batches) == 1
    assert batches[0][0]["embedding"] == [0.1, 0.2]


_TOKEN_BUDGET_FIELD_1 = _embeddable_field("root.desc", "First text")
_TOKEN_BUDGET_FIELD_2 = _embeddable_field("root.title", "Second text")


_TOKEN_BUDGET_FIELDS = [(ENTITY_ID, _TOKEN_BUDGET_FIELD_1), (ENTITY_ID, _TOKEN_BUDGET_FIELD_2)]


def test_upsert_token_budget_exceeded_flushes_before_adding(indexer: Indexer) -> None:
    """Two embeddable fields where second exceeds the token budget -> two separate batches."""

    def mock_encode(model, text):
        return [1] * 50  # 50 tokens each; budget = 100 * (1 - 0.1) = 90, so second overflows

    with (
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
        patch("orchestrator.core.search.indexing.indexer.get_max_tokens", return_value=100),
        patch("orchestrator.core.search.indexing.indexer.encode", side_effect=mock_encode),
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
        patch("orchestrator.core.search.indexing.indexer.get_max_tokens", return_value=10000),
        patch("orchestrator.core.search.indexing.indexer.encode", return_value=[1]),  # 1 token each
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
        patch("orchestrator.core.search.indexing.indexer.get_max_tokens", return_value=100),
        patch("orchestrator.core.search.indexing.indexer.encode", return_value=[1] * 200),  # > max_ctx=100
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
        patch("orchestrator.core.search.indexing.indexer.get_max_tokens", return_value=100),
        patch("orchestrator.core.search.indexing.indexer.encode", side_effect=Exception("tokenizer broken")),
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
        patch("orchestrator.core.search.indexing.indexer.get_max_tokens", return_value=100),
        patch("orchestrator.core.search.indexing.indexer.encode", return_value=[1, 2]),
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            return_value=[[0.5]],
        ),
    ):
        mock_llm.EMBEDDING_SAFE_MARGIN_PERCENT = 0.0
        mock_llm.EMBEDDING_MAX_BATCH_SIZE = None
        batches = list(indexer._generate_upsert_batches(_MIXED_FIELDS))

    assert len(batches) == 1
    assert len(batches[0]) == 2


# ---------------------------------------------------------------------------
# Indexer._flush_buffer
# ---------------------------------------------------------------------------


def test_flush_buffer_empty_embeddable_returns_non_embeddable_only(indexer: Indexer) -> None:
    non_emb_record: IndexableRecord = {
        "entity_id": ENTITY_ID,
        "entity_type": EntityType.SUBSCRIPTION.value,
        "entity_title": ENTITY_TITLE,
        "path": Ltree("root.insync"),
        "value": "true",
        "value_type": FieldType.BOOLEAN,
        "content_hash": "somehash",
        "embedding": None,
    }
    result = indexer._flush_buffer([], [non_emb_record])
    assert result == [non_emb_record]


def test_flush_buffer_empty_both_returns_empty(indexer: Indexer) -> None:
    result = indexer._flush_buffer([], [])
    assert result == []


def test_flush_buffer_with_embeddable_items(indexer: Indexer) -> None:
    field = _embeddable_field()
    buffer = [(ENTITY_ID, field)]

    with patch(
        "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
        return_value=[[0.1, 0.2]],
    ) as mock_embed:
        result = indexer._flush_buffer(buffer, [])

    mock_embed.assert_called_once()
    assert len(result) == 1
    assert result[0]["embedding"] == [0.1, 0.2]


def test_flush_buffer_combined_embeddable_and_non_embeddable(indexer: Indexer) -> None:
    field = _embeddable_field()
    buffer = [(ENTITY_ID, field)]
    non_emb_record: IndexableRecord = {
        "entity_id": ENTITY_ID,
        "entity_type": EntityType.SUBSCRIPTION.value,
        "entity_title": ENTITY_TITLE,
        "path": Ltree("root.insync"),
        "value": "true",
        "value_type": FieldType.BOOLEAN,
        "content_hash": "somehash",
        "embedding": None,
    }

    with patch(
        "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
        return_value=[[0.5]],
    ):
        result = indexer._flush_buffer(buffer, [non_emb_record])

    assert len(result) == 2
    assert result[0]["embedding"] is None
    assert result[1]["embedding"] == [0.5]


_MISMATCH_BUFFER = [
    (ENTITY_ID, _embeddable_field("root.a", "text a")),
    (ENTITY_ID, _embeddable_field("root.b", "text b")),
]


def test_flush_buffer_embedding_count_mismatch_raises(indexer: Indexer) -> None:
    with (
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            return_value=[[0.1]],  # only 1 embedding for 2 items
        ),
        pytest.raises(ValueError, match="Embedding mismatch"),
    ):
        indexer._flush_buffer(_MISMATCH_BUFFER, [])


def test_flush_buffer_dry_run_embeddings_are_empty(mock_config: MagicMock) -> None:
    """EmbeddingIndexer returns [] per text in dry_run; make sure no mismatch."""
    idx = Indexer(config=mock_config, dry_run=True, force_index=False, chunk_size=10)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE

    field = _embeddable_field()
    buffer = [(ENTITY_ID, field)]

    with patch(
        "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
        return_value=[[]],
    ):
        result = idx._flush_buffer(buffer, [])

    assert len(result) == 1
    # embedding=[] is falsy -> stored as None in _make_indexable_record
    assert result[0]["embedding"] is None


# ---------------------------------------------------------------------------
# Indexer._get_max_tokens
# ---------------------------------------------------------------------------


def test_get_max_tokens_returns_int_from_litellm(indexer: Indexer) -> None:
    with patch("orchestrator.core.search.indexing.indexer.get_max_tokens", return_value=8191):
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
        patch("orchestrator.core.search.indexing.indexer.get_max_tokens", **kwargs),
        patch("orchestrator.core.search.indexing.indexer.llm_settings") as mock_llm,
    ):
        mock_llm.EMBEDDING_FALLBACK_MAX_TOKENS = fallback
        mock_llm.EMBEDDING_MODEL = EMBEDDING_MODEL
        result = indexer._get_max_tokens()

    assert result == expected


def test_get_max_tokens_fallback_not_set_raises(indexer: Indexer) -> None:
    with (
        patch("orchestrator.core.search.indexing.indexer.get_max_tokens", side_effect=Exception("unknown")),
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
    embedding = [0.1, 0.2, 0.3]

    record = indexer._make_indexable_record(field, ENTITY_ID, embedding)

    assert record["entity_id"] == ENTITY_ID
    assert record["entity_type"] == EntityType.SUBSCRIPTION.value
    assert record["entity_title"] == ENTITY_TITLE
    assert record["path"] == Ltree("root.description")
    assert record["value"] == "Hello"
    assert record["value_type"] == FieldType.STRING
    assert isinstance(record["content_hash"], str)
    assert len(record["content_hash"]) == 64
    assert record["embedding"] == embedding


@pytest.mark.parametrize(
    "embedding",
    [
        pytest.param([], id="empty_list"),
        pytest.param(None, id="none"),
    ],
)
def test_make_indexable_record_falsy_embedding_stored_as_none(indexer: Indexer, embedding: list | None) -> None:
    """Falsy embeddings ([] or None) are stored as None."""
    field = ExtractedField(path="root.description", value="Hello", value_type=FieldType.STRING)
    record = indexer._make_indexable_record(field, ENTITY_ID, embedding)
    assert record["embedding"] is None


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
