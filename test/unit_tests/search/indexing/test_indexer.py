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

from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.db.models import SubscriptionTable, WorkflowApschedulerJob, WorkflowTable
from orchestrator.core.domain.context_cache import cache_subscription_models, get_from_cache, store_in_cache
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
    # Real table: _fetch_alive_ids builds a real select() against it, which a MagicMock column would reject.
    config.table = SubscriptionTable
    config.get_all_query.return_value = select(SubscriptionTable)
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
    """When a session is provided and no transaction is active, begin() must be used."""
    mock_session = MagicMock()
    mock_session.in_transaction.return_value = False
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
    with patch.object(idx, "_process_chunk", return_value=(0, 0, [])) as mock_proc:
        result = idx.run([])
    assert result == 0
    mock_proc.assert_not_called()


def test_run_single_entity_processes_once(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    idx = _make_indexer(mock_config, chunk_size=10)
    with patch.object(idx, "_process_chunk", return_value=(3, 0, [])) as mock_proc:
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
        return (len(chunk), 0, [])

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
        patch.object(idx, "_process_chunk", side_effect=lambda chunk, session=None: (len(chunk), 0, [])),
        patch("orchestrator.core.search.indexing.indexer._maybe_progress", side_effect=_fake_progress),
    ):
        idx.run(entities)

    mock_progress.update.assert_any_call(2)
    assert mock_progress.update.call_count == 2


def test_run_progress_none_does_not_update(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """When show_progress=False progress is None and update is not called."""
    idx = _make_indexer(mock_config)
    with patch.object(idx, "_process_chunk", return_value=(1, 0, [])):
        idx.run([mock_entity])
    # No AttributeError - confirms progress was None throughout


def test_run_dry_run_uses_nullcontext(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """dry_run=True should use nullcontext (no db.database_scope call)."""
    idx = _make_indexer(mock_config, dry_run=True)
    with (
        patch("orchestrator.core.search.indexing.indexer.db") as mock_db,
        patch.object(idx, "_process_chunk", return_value=(1, 0, [])),
    ):
        idx.run([mock_entity])
    mock_db.database_scope.assert_not_called()


def test_run_non_dry_run_uses_database_scope(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """dry_run=False should call db.database_scope()."""
    idx = _make_indexer(mock_config, dry_run=False)

    mock_database = MagicMock()
    mock_database.session = MagicMock()
    mock_database.session.in_transaction.return_value = False  # run()-owned

    @contextmanager
    def _fake_scope():
        yield mock_database

    with (
        patch("orchestrator.core.search.indexing.indexer.db") as mock_db,
        patch.object(idx, "_process_chunk", return_value=(1, 0, [])),
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

    with patch.object(idx, "_process_chunk", return_value=(3, 1, [])):
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
    assert result == (0, 0, [])


def test_process_chunk_with_fields_executes_batches(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """Non-dry-run with fields: session.execute should be called per batch."""
    idx = Indexer(config=mock_config, dry_run=False, force_index=True, chunk_size=10)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE

    mock_session = _write_session(alive_ids=[ENTITY_ID])
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
        patch.object(idx, "_determine_changes", return_value=([("eid", MagicMock())], [], 0, {})),
        patch.object(idx, "_generate_upsert_batches", return_value=iter([[fake_record]])),
    ):
        processed, identical, dropped = idx._process_chunk([mock_entity], session=mock_session)

    # lock, T1 hash recheck, existence recheck, insert
    assert mock_session.execute.call_count == 4
    assert processed == 1
    assert identical == 0
    assert dropped == []


def test_process_chunk_materializes_batches_before_lock(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """Upsert batches (and their embedding calls) are built before the advisory lock is taken."""
    idx = Indexer(config=mock_config, dry_run=False, force_index=True, chunk_size=10)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE
    events: list[str] = []

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

    def batch_generator(_fields_to_upsert):
        events.append("generate")
        yield [fake_record]

    mock_session = _write_session(alive_ids=[ENTITY_ID])
    inner_execute = mock_session.execute.side_effect

    def record_execute(stmt, params=None, **kwargs):
        text_ = str(stmt)
        if "pg_advisory_xact_lock" in text_:
            events.append("lock")
        elif "INSERT" in text_:
            events.append("upsert")
        return inner_execute(stmt, params, **kwargs)

    mock_session.execute.side_effect = record_execute
    with (
        patch.object(idx, "_determine_changes", return_value=([("eid", MagicMock())], [], 0, {})),
        patch.object(idx, "_generate_upsert_batches", side_effect=batch_generator),
    ):
        idx._process_chunk([mock_entity], session=mock_session)

    assert events == ["generate", "lock", "upsert"]


def test_process_chunk_delete_only_skips_batch_generation(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """A chunk with only stale paths to delete must not touch the embedding/batch pipeline."""
    idx = Indexer(config=mock_config, dry_run=False, force_index=False, chunk_size=10)
    mock_session = _write_session(alive_ids=[ENTITY_ID])
    stale = [(ENTITY_ID, Ltree("root.gone"))]
    batch_builder = MagicMock()

    with (
        patch.object(idx, "_determine_changes", return_value=([], stale, 0, {})),
        patch.object(idx, "_generate_upsert_batches", batch_builder),
    ):
        processed, identical, dropped = idx._process_chunk([mock_entity], session=mock_session)

    batch_builder.assert_not_called()
    assert processed == 0
    assert identical == 0
    assert dropped == []
    executed = [str(c.args[0]) for c in mock_session.execute.call_args_list]
    assert any("pg_advisory_xact_lock" in s for s in executed)
    # Delete-only chunks still revalidate (a concurrent reindex can cancel the delete),
    # but they never enter the embedding/batch pipeline.
    selects = [s for s in executed if s.lstrip().upper().startswith("SELECT") and "pg_advisory" not in s]
    assert len(selects) == 2
    delete_index = next(i for i, s in enumerate(executed) if s.strip().upper().startswith("DELETE"))
    assert all(executed.index(s) < delete_index for s in selects)


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
        patch.object(indexer, "_determine_changes", return_value=([("eid", MagicMock())], [], 0, {})),
        patch.object(indexer, "_generate_upsert_batches", return_value=iter([[fake_record]])),
    ):
        processed, identical, dropped = indexer._process_chunk([mock_entity], session=mock_session)

    # Dry-run takes no lock, writes nothing, and therefore performs no revalidation reads.
    mock_session.execute.assert_not_called()
    assert processed == 1
    assert dropped == []


def test_process_chunk_paths_to_delete_without_session_skips(indexer: Indexer, mock_entity: MagicMock) -> None:
    """If paths_to_delete is non-empty but session is None, _execute_batched_deletes is NOT called."""
    with (
        patch.object(
            indexer,
            "_determine_changes",
            return_value=([], [(ENTITY_ID, Ltree("root.old_path"))], 0, {}),
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
        patch.object(idx, "_determine_changes", return_value=([], paths, 0, {})),
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
    (_ENTITY_ID_1, "root.name", "hash_name_1"),
    (_ENTITY_ID_1, "root.status", "hash_status_1"),
    (_ENTITY_ID_2, "root.name", "hash_name_2"),
]


def test_get_all_existing_hashes_returns_dict_of_dicts(indexer: Indexer) -> None:
    mock_session = MagicMock()
    mock_session.execute.return_value.all.return_value = _HASH_DB_ROWS

    result = indexer._get_all_existing_hashes([_ENTITY_ID_1, _ENTITY_ID_2], mock_session)

    assert set(result.keys()) == {_ENTITY_ID_1, _ENTITY_ID_2}
    assert result[_ENTITY_ID_1] == {"root.name": "hash_name_1", "root.status": "hash_status_1"}
    assert result[_ENTITY_ID_2] == {"root.name": "hash_name_2"}


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
        patch("litellm.utils.get_max_tokens", return_value=100),
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


# ---------------------------------------------------------------------------
# _revalidate_planned_writes
# ---------------------------------------------------------------------------


def _record(entity_id: str, path: str, content_hash: str) -> IndexableRecord:
    return IndexableRecord(
        entity_id=entity_id,
        entity_type="subscription",
        entity_title=ENTITY_TITLE,
        path=Ltree(path),
        value="v",
        value_type=FieldType.STRING,
        content_hash=content_hash,
        embedding=None,
    )


def _revalidate(indexer: Indexer, records, deletes, baseline, t1_rows, alive_ids):
    """Drive _revalidate_planned_writes.

    The T1 hash scan comes from a MagicMock session's execute; existence is stubbed at the
    _fetch_alive_ids boundary because the mock config has no real table to build the select
    against. The real SQL is pinned in the integration tests.
    """
    session = MagicMock()
    hashes_result = MagicMock()
    hashes_result.all.return_value = t1_rows
    session.execute.return_value = hashes_result
    with patch.object(Indexer, "_fetch_alive_ids", return_value=set(alive_ids)):
        kept_batches, kept_deletes, dropped_ids = indexer._revalidate_planned_writes(
            [records] if records else [], deletes, baseline, session
        )
    return [r for batch in kept_batches for r in batch], kept_deletes, dropped_ids


def _write_session(hash_rows: list[tuple[str, str, str]] = (), alive_ids: list[str] | None = None) -> MagicMock:
    """A MagicMock session that answers the two under-lock revalidation reads.

    The T1 hash scan is the SELECT that mentions content_hash; the existence check is the
    (only) other SELECT and is answered with alive_ids. Lock/DELETE/INSERT get plain mocks.
    """
    session = MagicMock()
    alive_ids = [] if alive_ids is None else alive_ids

    def _execute(stmt, params=None, **kwargs):
        text_ = str(stmt).lstrip().upper()
        result = MagicMock()
        if text_.startswith("SELECT") and "CONTENT_HASH" in text_:
            result.all.return_value = list(hash_rows)
        elif text_.startswith("SELECT"):
            result.all.return_value = [(a,) for a in alive_ids]
        return result

    session.execute.side_effect = _execute
    return session


def test_revalidate_drops_upsert_overwritten_with_newer_value(mock_config: MagicMock, indexer: Indexer) -> None:
    rec = _record(ENTITY_ID, "root.note", "h_old")
    kept, _, dropped = _revalidate(
        indexer, [rec], [], {ENTITY_ID: {"root.note": "h_base"}}, [(ENTITY_ID, "root.note", "h_new")], [ENTITY_ID]
    )
    assert kept == []
    assert dropped == [ENTITY_ID]


@pytest.mark.parametrize(
    "stored,prepared",
    [
        pytest.param("h_old", "h_old", id="stored_equals_prepared"),
        pytest.param("h_base", "h_old", id="stored_equals_baseline"),
    ],
)
def test_revalidate_keeps_upsert_when_stored_equals_prepared_or_baseline(
    indexer: Indexer, stored: str, prepared: str
) -> None:
    rec = _record(ENTITY_ID, "root.note", prepared)
    kept, _, dropped = _revalidate(
        indexer, [rec], [], {ENTITY_ID: {"root.note": "h_base"}}, [(ENTITY_ID, "root.note", stored)], [ENTITY_ID]
    )
    assert kept == [rec]
    assert dropped == []


def test_revalidate_drops_upsert_when_entity_no_longer_exists(indexer: Indexer) -> None:
    rec = _record(ENTITY_ID, "root.fresh", "h_prepared")
    kept, _, dropped = _revalidate(indexer, [rec], [], {}, [], [])
    assert kept == []
    assert dropped == [ENTITY_ID]


def test_revalidate_drops_upsert_when_row_deleted_since_planning(indexer: Indexer) -> None:
    rec = _record(ENTITY_ID, "root.note", "h_old")
    kept, _, dropped = _revalidate(indexer, [rec], [], {ENTITY_ID: {"root.note": "h_base"}}, [], [ENTITY_ID])
    assert kept == []
    assert dropped == [ENTITY_ID]


def test_revalidate_keeps_fresh_path_for_alive_entity(indexer: Indexer) -> None:
    rec = _record(ENTITY_ID, "root.fresh", "h_prepared")
    kept, _, dropped = _revalidate(indexer, [rec], [], {}, [], [ENTITY_ID])
    assert kept == [rec]
    assert dropped == []


@pytest.mark.parametrize(
    "t1_rows,expected_kept",
    [
        pytest.param([(ENTITY_ID, "root.stale", "h_base")], True, id="unchanged_delete_kept"),
        pytest.param([(ENTITY_ID, "root.stale", "h_fresh")], False, id="reindexed_delete_cancelled"),
        pytest.param([], True, id="already_gone_delete_kept"),
    ],
)
def test_revalidate_cancelled_and_kept_deletes(indexer: Indexer, t1_rows, expected_kept: bool) -> None:
    delete = (ENTITY_ID, Ltree("root.stale"))
    _, kept_deletes, dropped = _revalidate(
        indexer, [], [delete], {ENTITY_ID: {"root.stale": "h_base"}}, t1_rows, [ENTITY_ID]
    )
    assert (kept_deletes == [delete]) is expected_kept
    assert dropped == []


def test_revalidate_force_mode_keeps_reindex_of_unchanged_rows(indexer: Indexer) -> None:
    rec = _record(ENTITY_ID, "root.note", "h_current")
    kept, _, dropped = _revalidate(indexer, [rec], [], {}, [(ENTITY_ID, "root.note", "h_current")], [ENTITY_ID])
    assert kept == [rec]
    assert dropped == []


# ---------------------------------------------------------------------------
# _process_chunk: revalidation wiring (Greptile P1 stale-write race)
# ---------------------------------------------------------------------------


def test_process_chunk_revalidates_after_lock_before_writes(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """Under the lock: lock -> T1 hash recheck -> existence recheck -> deletes -> upserts."""
    idx = Indexer(config=mock_config, dry_run=False, force_index=False, chunk_size=10)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE

    delete = (ENTITY_ID, Ltree("root.stale"))
    session = _write_session(
        hash_rows=[(ENTITY_ID, "root.note", "h_keep"), (ENTITY_ID, "root.stale", "h_base")],
        alive_ids=[ENTITY_ID],
    )
    events: list[str] = []
    inner_execute = session.execute.side_effect

    def spy(stmt, params=None, **kwargs):
        text_ = str(stmt).lstrip().upper()
        if "PG_ADVISORY_XACT_LOCK" in text_:
            events.append("lock")
        elif text_.startswith("SELECT") and "CONTENT_HASH" in text_:
            events.append("recheck_hashes")
        elif text_.startswith("SELECT"):
            events.append("recheck_existence")
        elif text_.startswith("DELETE"):
            events.append("delete")
        elif text_.startswith("INSERT"):
            events.append("upsert")
        return inner_execute(stmt, params, **kwargs)

    session.execute.side_effect = spy

    with (
        patch.object(
            idx,
            "_determine_changes",
            return_value=([("eid", MagicMock())], [delete], 0, {ENTITY_ID: {"root.stale": "h_base"}}),
        ),
        patch.object(idx, "_generate_upsert_batches", return_value=iter([[_record(ENTITY_ID, "root.note", "h_keep")]])),
    ):
        processed, _identical, dropped = idx._process_chunk([mock_entity], session=session)

    assert events == ["lock", "recheck_hashes", "recheck_existence", "delete", "upsert"]
    assert processed == 1
    assert dropped == []


def test_process_chunk_returns_dropped_ids_and_skips_stale_writes(
    mock_config: MagicMock, mock_entity: MagicMock
) -> None:
    """A record overwritten since planning is not written; its entity is returned for retry."""
    idx = Indexer(config=mock_config, dry_run=False, force_index=False, chunk_size=10)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE

    stale = _record(ENTITY_ID, "root.note", "h_old")
    fresh = _record(ENTITY_ID, "root.other", "h_other")
    session = _write_session(
        hash_rows=[(ENTITY_ID, "root.note", "h_new"), (ENTITY_ID, "root.other", "h_other")],
        alive_ids=[ENTITY_ID],
    )

    with (
        patch.object(
            idx,
            "_determine_changes",
            return_value=([("eid", MagicMock())], [], 0, {ENTITY_ID: {"root.note": "h_base"}}),
        ),
        patch.object(idx, "_generate_upsert_batches", return_value=iter([[stale, fresh]])),
    ):
        processed, _identical, dropped = idx._process_chunk([mock_entity], session=session)

    inserts = [c for c in session.execute.call_args_list if "INSERT" in str(c.args[0])]
    assert len(inserts) == 1
    assert [r["path"] for r in inserts[0].args[1]] == [Ltree("root.other")]
    assert processed == 1
    assert dropped == [ENTITY_ID]


def test_process_chunk_force_index_keeps_unchanged_rows(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """Force mode has no baseline; stored==prepared must be written, never self-dropped."""
    idx = Indexer(config=mock_config, dry_run=False, force_index=True, chunk_size=10)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE

    record = _record(ENTITY_ID, "root.note", "h_current")
    session = _write_session(hash_rows=[(ENTITY_ID, "root.note", "h_current")], alive_ids=[ENTITY_ID])

    with (
        patch.object(idx, "_determine_changes", return_value=([("eid", MagicMock())], [], 0, {})),
        patch.object(idx, "_generate_upsert_batches", return_value=iter([[record]])),
    ):
        processed, _identical, dropped = idx._process_chunk([mock_entity], session=session)

    assert any("INSERT" in str(c.args[0]) for c in session.execute.call_args_list)
    assert processed == 1
    assert dropped == []


# ---------------------------------------------------------------------------
# run(): single bounded retry of dropped entities
# ---------------------------------------------------------------------------


@contextmanager
def _fake_database_scope(mock_database: MagicMock):
    yield mock_database


def _retry_setup(mock_config: MagicMock) -> tuple[Indexer, MagicMock]:
    """Indexer plus the MagicMock database its faked db.database_scope() yields."""
    idx = Indexer(config=mock_config, dry_run=False, force_index=False, chunk_size=10)
    idx.logger = MagicMock()
    mock_database = MagicMock()
    mock_database.session.execute.return_value.scalars.return_value.all.return_value = [MagicMock()]
    mock_database.session.in_transaction.return_value = False  # run()-owned
    return idx, mock_database


def test_run_retries_dropped_entities_once(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """Ids dropped by revalidation are reloaded and reprocessed exactly one extra time."""
    idx, mock_database = _retry_setup(mock_config)
    passes: list[int] = []

    def fake_process_chunk(chunk, session=None):
        passes.append(1)
        # first pass drops the entity; the retry pass (fresh state) succeeds
        return (1, 0, [ENTITY_ID]) if len(passes) == 1 else (1, 0, [])

    with (
        patch("orchestrator.core.search.indexing.indexer.db") as mock_db,
        patch.object(idx, "_process_chunk", side_effect=fake_process_chunk),
    ):
        mock_db.database_scope.return_value = _fake_database_scope(mock_database)
        result = idx.run([mock_entity])

    assert len(passes) == 2
    mock_config.get_all_query.assert_called_once_with(None)
    assert result == 2
    assert idx._dropped_entity_ids == set()
    idx.logger.warning.assert_not_called()


def test_retry_second_pass_drops_are_logged_and_not_requeued(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """Work dropped again during the retry is abandoned with a warning; the pass never loops."""
    idx, mock_database = _retry_setup(mock_config)
    passes: list[int] = []

    def fake_process_chunk(chunk, session=None):
        passes.append(1)
        return (1, 0, [ENTITY_ID])  # drops on every pass

    with (
        patch("orchestrator.core.search.indexing.indexer.db") as mock_db,
        patch.object(idx, "_process_chunk", side_effect=fake_process_chunk),
    ):
        mock_db.database_scope.return_value = _fake_database_scope(mock_database)
        result = idx.run([mock_entity])

    assert len(passes) == 2  # main pass + exactly one retry
    assert result == 2
    idx.logger.warning.assert_called_once()
    assert idx._dropped_entity_ids == set()


@pytest.mark.parametrize(
    "dry_run,dropped",
    [
        pytest.param(False, set(), id="nothing_dropped"),
        pytest.param(True, {ENTITY_ID}, id="dry_run"),
    ],
)
def test_retry_skipped_when_nothing_dropped_or_dry_run(
    mock_config: MagicMock, mock_entity: MagicMock, dry_run: bool, dropped: set[str]
) -> None:
    """The retry pass only runs for a real run that actually dropped work."""
    idx = _make_indexer(mock_config, dry_run=dry_run)
    idx._dropped_entity_ids.update(dropped)
    mock_database = MagicMock()
    mock_database.session.in_transaction.return_value = False  # run()-owned

    with (
        patch("orchestrator.core.search.indexing.indexer.db") as mock_db,
        patch.object(idx, "_process_chunk", return_value=(1, 0, list(dropped) if dry_run else [])),
    ):
        mock_db.database_scope.return_value = _fake_database_scope(mock_database)
        idx.run([mock_entity])

    mock_config.get_all_query.assert_not_called()


# ---------------------------------------------------------------------------
# _determine_changes: source-fresh planning (streamed-snapshot race)
# ---------------------------------------------------------------------------


def test_determine_changes_reads_baselines_before_reloading(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """The ordering IS the fix: baseline first, then the fresh source read."""
    idx = _make_indexer(mock_config, dry_run=False)
    calls: list[str] = []

    def fake_hashes(_ids, _session=None):
        calls.append("hashes")
        return {}

    def fake_load(_ids, _session=None):
        calls.append("load")
        return [mock_entity]

    with (
        patch.object(idx, "_get_all_existing_hashes", side_effect=fake_hashes),
        patch.object(idx, "_load_source_entities", side_effect=fake_load),
    ):
        idx._determine_changes([mock_entity], session=MagicMock())

    assert calls == ["hashes", "load"]


def test_determine_changes_traverses_reloaded_entities(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """On the write path the plan is built from the reloaded rows, not the stream objects."""
    idx = _make_indexer(mock_config, dry_run=False)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE
    reloaded = MagicMock()  # distinct object: proves WHICH row the traversal consumed
    reloaded.subscription_id = UUID(ENTITY_ID)
    loaded: list[list[str]] = []

    def fake_load(ids, _session=None):
        loaded.append(list(ids))
        return [reloaded]

    with (
        patch.object(idx, "_get_all_existing_hashes", return_value={}),
        patch.object(idx, "_load_source_entities", side_effect=fake_load),
    ):
        fields, deletes, _identical, _baseline = idx._determine_changes([mock_entity], session=MagicMock())

    assert loaded == [[ENTITY_ID]]
    traversed = [c.args[0] for c in mock_config.traverser.get_fields.call_args_list]
    assert traversed == [reloaded]
    assert len(fields) == 3
    assert deletes == []


def test_determine_changes_skips_missing_entities_without_planning(mock_config: MagicMock) -> None:
    """Entities that disappeared before planning are not planned; the baseline still returns."""
    idx = _make_indexer(mock_config, dry_run=False)
    stored = {ENTITY_ID: {"root.gone": "h"}}

    with (
        patch.object(idx, "_get_all_existing_hashes", return_value=stored),
        patch.object(idx, "_load_source_entities", return_value=[]),
    ):
        fields, deletes, _identical, baseline = idx._determine_changes([MagicMock()], session=MagicMock())

    assert fields == []
    assert deletes == []
    assert baseline == stored


@pytest.mark.parametrize(
    "dry_run,session",
    [pytest.param(True, MagicMock(), id="dry_run"), pytest.param(False, None, id="no_session")],
)
def test_determine_changes_no_reload_for_dry_run_or_no_session(
    mock_config: MagicMock, mock_entity: MagicMock, dry_run: bool, session: MagicMock | None
) -> None:
    """Read-only paths keep traversing what they were handed: no extra source read."""
    idx = _make_indexer(mock_config, dry_run=dry_run)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE
    load_spy = MagicMock()

    with (
        patch("orchestrator.core.search.indexing.indexer.db"),
        patch.object(idx, "_get_all_existing_hashes", return_value={}),
        patch.object(idx, "_load_source_entities", load_spy),
    ):
        fields, _deletes, _identical, _baseline = idx._determine_changes([mock_entity], session=session)

    load_spy.assert_not_called()
    assert len(fields) == 3


def test_determine_changes_force_mode_returns_real_baselines_but_forces_all_fields(
    mock_config: MagicMock, mock_entity: MagicMock, mock_fields: list[ExtractedField]
) -> None:
    """Force mode must still repair drifted rows: real stored baselines, every field forced, no deletes."""
    idx = Indexer(config=mock_config, dry_run=False, force_index=True, chunk_size=10)
    stored = {
        ENTITY_ID: {
            f.path: Indexer._compute_content_hash(f.path, f.value, f.value_type, ENTITY_TITLE) for f in mock_fields
        }
    }
    stored[ENTITY_ID]["root.gone"] = "h"

    with (
        patch.object(idx, "_get_all_existing_hashes", return_value=stored),
        patch.object(idx, "_load_source_entities", return_value=[mock_entity]),
    ):
        fields, deletes, identical, baseline = idx._determine_changes([MagicMock()], session=MagicMock())

    assert len(fields) == 3
    assert identical == 0
    assert deletes == []
    assert baseline == stored


# ---------------------------------------------------------------------------
# _fetch_alive_ids: config-faithful existence SQL
# ---------------------------------------------------------------------------


def test_fetch_alive_ids_preserves_config_filters(indexer: Indexer) -> None:
    """The existence check must run through the config's query, soft-delete filter included."""
    indexer.config.pk_name = "workflow_id"
    indexer.config.table = WorkflowTable
    indexer.config.get_all_query.return_value = WorkflowTable.select()
    session = MagicMock()
    session.execute.return_value.all.return_value = []

    indexer._fetch_alive_ids([ENTITY_ID], session)

    sql = str(session.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "deleted_at IS NULL" in sql
    assert "workflow_id IN" in sql


def test_fetch_alive_ids_binds_string_ids_for_schedule(indexer: Indexer) -> None:
    """Schedule ids live in a String(512) column: binding them as UUID breaks in PostgreSQL."""
    indexer.config.pk_name = "schedule_id"
    indexer.config.table = WorkflowApschedulerJob
    indexer.config.get_all_query.return_value = select(WorkflowApschedulerJob)
    session = MagicMock()
    session.execute.return_value.all.return_value = []

    indexer._fetch_alive_ids(["some-schedule-id"], session)

    stmt = session.execute.call_args.args[0]
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "::UUID" not in sql
    assert "'some-schedule-id'" in sql


# ---------------------------------------------------------------------------
# _revalidate_planned_writes: per-reason drop summary
# ---------------------------------------------------------------------------


def test_revalidate_logs_per_reason_drop_counts(indexer: Indexer) -> None:
    indexer.logger = MagicMock()
    rec_overwritten = _record("e1", "root.note", "h_old")
    rec_deleted_entity = _record("e2", "root.fresh", "h_p")
    rec_row_removed = _record("e3", "root.note", "h_old")
    cancelled_delete = ("e4", Ltree("root.stale"))
    baseline = {
        "e1": {"root.note": "h_base"},
        "e3": {"root.note": "h_base"},
        "e4": {"root.stale": "h_base"},
    }
    t1_rows = [
        ("e1", "root.note", "h_new"),
        ("e3", "root.gone", "h_x"),  # e3.root.note row removed since planning
        ("e4", "root.stale", "h_fresh"),  # reindexed -> delete cancelled
    ]
    _, _, dropped = _revalidate(
        indexer,
        [rec_overwritten, rec_deleted_entity, rec_row_removed],
        [cancelled_delete],
        baseline,
        t1_rows,
        ["e1", "e3"],
    )

    assert dropped == ["e1", "e2", "e3"]
    indexer.logger.info.assert_called_once()
    kwargs = indexer.logger.info.call_args.kwargs
    assert kwargs["overwritten_by_newer"] == 1
    assert kwargs["entity_deleted"] == 1
    assert kwargs["row_removed_since_planning"] == 1
    assert kwargs["delete_cancelled"] == 1


def test_revalidate_silent_when_nothing_dropped(indexer: Indexer) -> None:
    indexer.logger = MagicMock()
    rec = _record(ENTITY_ID, "root.note", "h_same")
    kept, _, dropped = _revalidate(
        indexer, [rec], [], {ENTITY_ID: {"root.note": "h_base"}}, [(ENTITY_ID, "root.note", "h_same")], [ENTITY_ID]
    )
    assert kept == [rec] and dropped == []
    indexer.logger.info.assert_not_called()


# ---------------------------------------------------------------------------
# _retry_dropped: fresh reload per partition, inside the transaction
# ---------------------------------------------------------------------------


def test_retry_partitions_ids_by_chunk_size(mock_config: MagicMock) -> None:
    """The retry reloads at most chunk_size ids per query, never all drops at once."""
    idx = Indexer(config=mock_config, dry_run=False, force_index=False, chunk_size=2)
    idx._dropped_entity_ids.update({"a", "b", "c"})
    loaded: list[list[str]] = []

    def fake_load(ids: list[str], _session: MagicMock | None = None) -> list:
        loaded.append(list(ids))
        return []

    with patch.object(idx, "_load_source_entities", side_effect=fake_load):
        session = MagicMock()
        session.in_transaction.return_value = False  # run()-owned: per-partition transactions
        processed, identical = idx._retry_dropped(session)

    assert loaded == [["a", "b"], ["c"]]
    assert (processed, identical) == (0, 0)


def test_retry_begins_transaction_before_reloading(mock_config: MagicMock) -> None:
    """The reload query must run inside the transaction it opened, never before it.

    Executing SQL outside session.begin() autobegins, and the subsequent begin()
    then raises InvalidRequestError on a real Session.
    """
    idx = Indexer(config=mock_config, dry_run=False, force_index=False, chunk_size=2)
    idx._dropped_entity_ids.update({"a", "b", "c"})
    order: list[str] = []

    @contextmanager
    def fake_begin(_session: MagicMock, *, allow_borrow: bool = True) -> Generator[None, None, None]:
        assert not allow_borrow
        order.append("begin")
        yield

    def fake_load(_ids: list[str], _session: MagicMock | None = None) -> list:
        order.append("load")
        return []

    with (
        patch("orchestrator.core.search.indexing.indexer._maybe_begin", fake_begin),
        patch.object(idx, "_load_source_entities", side_effect=fake_load),
    ):
        session = MagicMock()
        session.in_transaction.return_value = False  # run()-owned: per-partition transactions
        idx._retry_dropped(session)

    assert order == ["begin", "load", "begin", "load"]


def test_retry_runs_with_fresh_subscription_models(mock_config: MagicMock) -> None:
    """Retry replanning must not observe first-pass cached subscription models.

    Asserted by behavior INSIDE a nonempty retry pass: a model cached before the retry
    must be invisible to code running within the retry, and visible again after it.
    """
    idx = Indexer(config=mock_config, dry_run=False, force_index=False, chunk_size=10)
    idx._dropped_entity_ids.add(ENTITY_ID)
    cached = MagicMock()
    cached.subscription_id = UUID(ENTITY_ID)
    observed: dict[str, object] = {}

    def fake_process(rows, session):
        observed["inside"] = get_from_cache(UUID(ENTITY_ID))
        return (len(rows), 0, [])

    with cache_subscription_models():
        store_in_cache(cached)
        session = MagicMock()
        session.in_transaction.return_value = False  # run()-owned: retry proceeds
        with (
            patch.object(idx, "_load_source_entities", return_value=[MagicMock()]),
            patch.object(idx, "_process_chunk", side_effect=fake_process),
        ):
            processed, _identical = idx._retry_dropped(session)
        observed["after"] = get_from_cache(UUID(ENTITY_ID))

    assert processed == 1
    assert observed["inside"] is None  # cache bypassed for the whole retry pass
    assert observed["after"] is cached  # outer cache restored afterwards


# ---------------------------------------------------------------------------
# Round 2 re-review regressions: transaction ownership, dry-run deletes,
# subscription model cache eviction on source reload
# ---------------------------------------------------------------------------


def test_maybe_begin_strict_mode_rejects_foreign_transaction() -> None:
    """allow_borrow=False must raise instead of silently joining a transaction it does not own.

    run()'s write session is its own; an active transaction there can only come from a
    lazy entities iterable that queried the same scoped session — joining it would mean
    nobody ever commits, so the writes roll back silently.
    """
    session = MagicMock()
    session.in_transaction.return_value = True
    with pytest.raises(RuntimeError, match="materialize"):
        with _maybe_begin(session, allow_borrow=False):
            pass


def test_maybe_begin_borrows_active_caller_transaction() -> None:
    """A session whose transaction is already active is joined, not begun again."""
    mock_session = MagicMock()
    mock_session.in_transaction.return_value = True

    with _maybe_begin(mock_session):
        pass

    mock_session.begin.assert_not_called()


def test_maybe_begin_strict_mode_rejects_external_connection_transaction() -> None:
    """An idle Session does not own the transaction already open on its bound Connection."""
    session = MagicMock()
    session.in_transaction.return_value = False
    connection = MagicMock(spec=Connection)
    connection.in_transaction.return_value = True
    session.get_bind.return_value = connection

    with pytest.raises(RuntimeError, match="externally.*transaction"):
        with _maybe_begin(session, allow_borrow=False):
            pass

    session.begin.assert_not_called()
    session.connection.assert_not_called()  # checking ownership must not autobegin
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_retry_skips_idle_session_with_external_connection_transaction(mock_config: MagicMock) -> None:
    """Session-level commit cannot release a lock held by an outer Connection transaction."""
    idx = _make_indexer(mock_config, dry_run=False)
    idx._dropped_entity_ids = {ENTITY_ID}
    idx.logger = MagicMock()
    session = MagicMock()
    session.in_transaction.return_value = False
    connection = MagicMock(spec=Connection)
    connection.in_transaction.return_value = True
    session.get_bind.return_value = connection

    with patch.object(idx, "_load_source_entities", return_value=[]) as reload:
        result = idx._retry_dropped(session)

    assert result == (0, 0)
    reload.assert_not_called()
    session.begin.assert_not_called()
    session.connection.assert_not_called()
    assert not idx._dropped_entity_ids
    assert idx.logger.warning.call_args.kwargs["reason"] == "external_connection_transaction"
    assert idx.logger.warning.call_args.kwargs["dropped_entity_ids"] == [ENTITY_ID]


def test_dry_run_with_session_does_not_execute_deletes(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """Dry-run must not delete index rows even when the caller supplies a session."""
    idx = _make_indexer(mock_config, dry_run=True)
    session = MagicMock()
    planned_delete = (ENTITY_ID, Ltree("root.gone"))
    with patch.object(idx, "_determine_changes", return_value=([], [planned_delete], 0, {})):
        processed, _identical, dropped = idx._process_chunk([mock_entity], session=session)

    assert processed == 0
    assert dropped == []
    session.execute.assert_not_called()


def test_load_source_entities_evicts_subscription_models(mock_config: MagicMock) -> None:
    """Planned subscription ids are evicted so the traverser rebuilds models from fresh state."""
    idx = _make_indexer(mock_config, dry_run=False)
    with patch("orchestrator.core.search.indexing.indexer.evict_from_cache") as evict:
        idx._load_source_entities([ENTITY_ID], MagicMock())
    evict.assert_called_once_with([ENTITY_ID])


def test_load_source_entities_does_not_evict_non_subscription_ids() -> None:
    """Schedule ids are plain strings: they must never reach the UUID-keyed cache eviction."""
    config = MagicMock()
    config.entity_kind = EntityType.SCHEDULE
    config.pk_name = "schedule_id"
    config.table = WorkflowApschedulerJob
    config.get_all_query.return_value = select(WorkflowApschedulerJob)
    idx = Indexer(config=config, dry_run=False, force_index=False, chunk_size=10)
    with patch("orchestrator.core.search.indexing.indexer.evict_from_cache") as evict:
        idx._load_source_entities(["not-a-uuid"], MagicMock())
    evict.assert_not_called()


def test_retry_dropped_skipped_when_transaction_borrowed(mock_config: MagicMock) -> None:
    """A borrowed caller transaction may already hold the advisory lock from an earlier pass.

    Embedding under that lock would block all same-type hooks, so the retry is skipped
    and the dropped ids are surfaced in a warning; the next scheduled reindex converges.
    """
    idx = _make_indexer(mock_config, dry_run=False, chunk_size=1)
    idx.logger = MagicMock()
    session = MagicMock()
    session.in_transaction.return_value = True
    idx._dropped_entity_ids = {ENTITY_ID, "87654321-4321-4321-4321-cba876543210"}

    with patch.object(idx, "_process_chunk") as mock_chunk:
        processed, identical = idx._retry_dropped(session)

    assert (processed, identical) == (0, 0)
    mock_chunk.assert_not_called()
    assert not idx._dropped_entity_ids
    warning = next(c for c in idx.logger.warning.call_args_list if "retry" in str(c.args[0]).lower())
    assert sorted(warning.kwargs["dropped_entity_ids"]) == sorted([ENTITY_ID, "87654321-4321-4321-4321-cba876543210"])


def test_retry_dropped_keeps_partitions_when_it_owns_the_transaction(mock_config: MagicMock) -> None:
    """run()-owned sessions keep per-partition begin/commit so each lock is released before the next embedding."""
    idx = _make_indexer(mock_config, dry_run=False, chunk_size=1)
    session = MagicMock()
    session.in_transaction.return_value = False
    idx._dropped_entity_ids = {ENTITY_ID, "87654321-4321-4321-4321-cba876543210"}
    partitions: list[int] = []

    def fake_chunk(rows, _session):
        partitions.append(len(rows))
        return len(rows), 0, []

    with (
        patch.object(idx, "_load_source_entities", side_effect=lambda ids, _s: [MagicMock() for _ in ids]),
        patch.object(idx, "_process_chunk", side_effect=fake_chunk),
    ):
        idx._retry_dropped(session)

    assert partitions == [1, 1]
    assert session.begin.call_count == 2


# ---------------------------------------------------------------------------
# Round 5 re-review regressions: isolation level, pending-edit reload, drop accumulation
# ---------------------------------------------------------------------------


def test_determine_changes_rejects_unflushed_planned_source_edit(
    mock_config: MagicMock, mock_entity: MagicMock
) -> None:
    """The source-fresh reload uses populate_existing, which silently discards unflushed edits.

    A pending edit on the planning session for a planned row would be overwritten by the
    reload and lost on the caller's next commit; planning must refuse instead.
    """
    idx = _make_indexer(mock_config, dry_run=False)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE
    pending = SubscriptionTable(subscription_id=UUID(ENTITY_ID))
    pending.description = "pending-edit"
    session = MagicMock()
    session.dirty = [pending]

    with patch.object(idx, "_get_all_existing_hashes", return_value={}), pytest.raises(RuntimeError, match="flush"):
        idx._determine_changes([mock_entity], session=session)


@pytest.mark.parametrize("pending_state", ["dirty", "new", "deleted"])
def test_determine_changes_rejects_unrelated_pending_changes(
    mock_config: MagicMock, mock_entity: MagicMock, pending_state: str
) -> None:
    """Reject any pending state, not just pending changes to the planned roots.

    Autoflush moves pending state mid-plan, and the source-fresh reload eager-loads and
    reverts related rows (e.g. a scheduled subscription's workflow). The contract is
    therefore "plan on a session with no pending changes".
    """
    idx = _make_indexer(mock_config, dry_run=False)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE
    unrelated = SubscriptionTable(subscription_id=uuid4())
    unrelated.description = "someone else's edit"
    session = MagicMock()
    setattr(session, pending_state, [unrelated])

    with (
        patch.object(idx, "_get_all_existing_hashes", return_value={}) as baseline,
        patch.object(idx, "_load_source_entities", return_value=[]),
        pytest.raises(RuntimeError, match="pending"),
    ):
        idx._determine_changes([mock_entity], session=session)
    baseline.assert_not_called()  # even this SELECT could autoflush the pending state


@pytest.mark.parametrize("level", ["READ COMMITTED", "READ UNCOMMITTED"])
def test_process_chunk_rejects_dbapi_autocommit_before_embedding(
    mock_config: MagicMock, mock_entity: MagicMock, level: str
) -> None:
    """A DBAPI-autocommit connection releases pg_advisory_xact_lock at the statement end.

    get_isolation_level() never reports AUTOCOMMIT (it answers READ COMMITTED), so the
    DBAPI autocommit must be checked independently before embedding or locking.
    """
    idx = _make_indexer(mock_config, dry_run=False)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE
    session = MagicMock()
    session.connection.return_value.get_isolation_level.return_value = level
    session.connection.return_value.connection.dbapi_connection.autocommit = True
    field = _embeddable_field()

    with (
        patch.object(idx, "_determine_changes", return_value=([(ENTITY_ID, field)], [], 0, {})),
        patch.object(idx, "_generate_upsert_batches", return_value=[]) as embed,
        patch.object(idx, "_revalidate_planned_writes", return_value=([], [], [])) as revalidate,
        patch("orchestrator.core.search.indexing.indexer.acquire_search_index_write_lock") as lock,
        pytest.raises(RuntimeError, match="advisory lock"),
    ):
        idx._process_chunk([mock_entity], session=session)
    embed.assert_not_called()
    lock.assert_not_called()
    revalidate.assert_not_called()


@pytest.mark.parametrize("level", ["REPEATABLE READ", "SERIALIZABLE"])
def test_process_chunk_rejects_repeatable_read_session(
    mock_config: MagicMock, mock_entity: MagicMock, level: str
) -> None:
    """Under REPEATABLE READ the under-lock recheck sees the pre-plan snapshot: reject before embedding."""
    idx = _make_indexer(mock_config, dry_run=False)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE
    session = MagicMock()
    session.connection.return_value.get_isolation_level.return_value = level
    field = _embeddable_field()

    with (
        patch.object(idx, "_determine_changes", return_value=([(ENTITY_ID, field)], [], 0, {})),
        patch.object(idx, "_generate_upsert_batches") as embed,
        pytest.raises(RuntimeError, match="READ COMMITTED"),
    ):
        idx._process_chunk([mock_entity], session=session)
    embed.assert_not_called()


@pytest.mark.parametrize("level", ["READ COMMITTED", "READ UNCOMMITTED"])
def test_process_chunk_accepts_read_committed_session(
    mock_config: MagicMock, mock_entity: MagicMock, level: str
) -> None:
    """READ COMMITTED (PostgreSQL's default) proceeds untouched."""
    idx = _make_indexer(mock_config, dry_run=False)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE
    session = MagicMock()
    session.connection.return_value.get_isolation_level.return_value = level
    session.connection.return_value.connection.dbapi_connection.autocommit = False
    field = _embeddable_field()

    with (
        patch.object(idx, "_determine_changes", return_value=([(ENTITY_ID, field)], [], 0, {})),
        patch.object(idx, "_generate_upsert_batches", return_value=[]),
        patch.object(idx, "_revalidate_planned_writes", return_value=([], [], [])),
        patch("orchestrator.core.search.indexing.indexer.acquire_search_index_write_lock"),
    ):
        processed, identical, dropped = idx._process_chunk([mock_entity], session=session)

    assert (processed, identical, dropped) == (0, 0, [])


def test_subscription_attempt_expires_after_baseline_and_restores_cache_on_failure(
    mock_config: MagicMock, mock_entity: MagicMock
) -> None:
    """Expiry before baseline or inherited cache reuse can admit pre-baseline values."""
    idx = _make_indexer(mock_config, dry_run=False)
    session = MagicMock()
    calls = []
    dependency = MagicMock(subscription_id=uuid4())

    def baseline(*_args):
        calls.append("baseline")
        return {}

    def reload(*_args):
        calls.append("reload")
        return [mock_entity]

    def traverse(*_args, **_kwargs):
        calls.append("traverse")
        assert get_from_cache(dependency.subscription_id) is None
        store_in_cache(MagicMock(subscription_id=dependency.subscription_id))
        raise ValueError("traversal failed")

    session.expire_all.side_effect = lambda: calls.append("expire")
    with cache_subscription_models():
        store_in_cache(dependency)
        with (
            patch.object(idx, "_get_all_existing_hashes", side_effect=baseline),
            patch.object(idx, "_load_source_entities", side_effect=reload),
            patch.object(mock_config.traverser, "get_fields", side_effect=traverse),
            pytest.raises(ValueError, match="traversal failed"),
        ):
            idx._determine_changes([mock_entity], session)
        assert get_from_cache(dependency.subscription_id) is dependency
    assert calls == ["baseline", "expire", "reload", "traverse"]


@pytest.mark.parametrize("path", ["dry_run", "no_session", "non_subscription"])
def test_planning_does_not_expire_read_only_or_other_entity_state(
    mock_config: MagicMock, mock_entity: MagicMock, path: str
) -> None:
    """Only clean subscription write planning owns the attempt-wide ORM expiration."""
    idx = _make_indexer(mock_config, dry_run=path == "dry_run")
    if path == "non_subscription":
        mock_config.entity_kind = EntityType.WORKFLOW
    session = MagicMock()
    with (
        patch("orchestrator.core.search.indexing.indexer.db", session=session),
        patch.object(idx, "_get_all_existing_hashes", return_value={}),
        patch.object(idx, "_load_source_entities", return_value=[mock_entity]),
    ):
        fields, _, _, _ = idx._determine_changes([mock_entity], None if path == "no_session" else session)
    assert fields
    session.expire_all.assert_not_called()


def test_run_does_not_carry_dropped_ids_into_the_next_run(mock_config: MagicMock, mock_entity: MagicMock) -> None:
    """A failed run's collected drops must not resurface inside a later, unrelated run."""
    idx = Indexer(config=mock_config, dry_run=False, force_index=False, chunk_size=1)
    idx.logger = MagicMock()
    mock_database = MagicMock()
    mock_database.session.in_transaction.return_value = False
    calls = {"n": 0}

    def first_run(chunk, session=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return (1, 0, [ENTITY_ID])
        raise ValueError("boom")

    with (
        patch("orchestrator.core.search.indexing.indexer.db") as mock_db,
        patch.object(idx, "_process_chunk", side_effect=first_run),
    ):
        mock_db.database_scope.return_value = _fake_database_scope(mock_database)
        with pytest.raises(ValueError, match="boom"):
            idx.run([MagicMock(), mock_entity])
    assert idx._dropped_entity_ids == {ENTITY_ID}  # the failed run leaves its drops behind...

    with (
        patch("orchestrator.core.search.indexing.indexer.db") as mock_db,
        patch.object(idx, "_process_chunk", return_value=(1, 0, [])),
        patch.object(idx, "_retry_dropped") as retry,
    ):
        mock_db.database_scope.return_value = _fake_database_scope(mock_database)
        result = idx.run([mock_entity])

    retry.assert_not_called()  # ...but the next run must not silently reindex them
    assert result == 1
    assert idx._dropped_entity_ids == set()
