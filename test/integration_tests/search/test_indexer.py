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

"""Tests for Indexer public API.

Content hashing, text preparation, record creation, change detection,
force index, token counting, dry run, batch generation, and error handling.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchEmbedding, AiSearchIndex
from orchestrator.core.search.core.types import EntityType, ExtractedField, FieldType
from orchestrator.core.search.indexing.indexer import Indexer, StoredHashes
from orchestrator.core.settings import llm_settings

# Test constants
ENTITY_ID = "12345678-1234-1234-1234-123456789abc"
ENTITY_TITLE = "Test Title"


@pytest.fixture
def mock_fields():
    """Create mock fields that would be returned by a traverser."""
    return [
        ExtractedField(path="description", value="Test subscription", value_type=FieldType.STRING),
        ExtractedField(path="status", value="active", value_type=FieldType.STRING),
        ExtractedField(path="insync", value="true", value_type=FieldType.BOOLEAN),
    ]


@pytest.fixture
def mock_entity():
    """Create a mock database entity."""
    entity = MagicMock()
    entity.subscription_id = UUID(ENTITY_ID)
    entity.description = "Test subscription"
    entity.status = "active"
    entity.insync = True
    return entity


@pytest.fixture
def mock_config(mock_fields):
    """Create a mock entity configuration."""
    config = MagicMock()
    config.entity_kind = EntityType.SUBSCRIPTION
    config.pk_name = "subscription_id"
    config.root_name = "subscription"
    config.traverser.get_fields.return_value = mock_fields
    config.get_title_from_fields.return_value = ENTITY_TITLE
    return config


@pytest.fixture
def indexer(mock_config):
    """Create an indexer instance for testing."""
    idx = Indexer(config=mock_config, dry_run=True, force_index=False, chunk_size=10)
    idx._entity_titles[ENTITY_ID] = ENTITY_TITLE
    return idx


@pytest.fixture
def matching_hashes(mock_fields):
    """Hashes that match mock_entity fields."""
    return {
        ENTITY_ID: {
            field.path: StoredHashes(
                Indexer._compute_content_hash(field.path, field.value, field.value_type, ENTITY_TITLE), None
            )
            for field in mock_fields
        }
    }


# ---------------------------------------------------------------------------
# Content hashing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path1", "value1", "path2", "value2", "should_match"),
    [
        pytest.param("path", "value", "path", "value", True, id="deterministic_same_inputs"),
        pytest.param("path", "value1", "path", "value2", False, id="different_values"),
        pytest.param("path1", "value", "path2", "value", False, id="different_paths"),
        pytest.param("path", None, "path", None, True, id="none_values_deterministic"),
    ],
)
def test_compute_content_hash(path1, value1, path2, value2, should_match):
    """Test content hash is deterministic and sensitive to path/value changes."""
    hash1 = Indexer._compute_content_hash(path1, value1, FieldType.STRING, "title")
    hash2 = Indexer._compute_content_hash(path2, value2, FieldType.STRING, "title")

    assert isinstance(hash1, str)
    assert len(hash1) == 64  # SHA256

    if should_match:
        assert hash1 == hash2
    else:
        assert hash1 != hash2


# ---------------------------------------------------------------------------
# Text preparation
# ---------------------------------------------------------------------------


def test_prepare_text_for_embedding():
    """Test text preparation combines path and value."""
    field = ExtractedField(path="description", value="Test value", value_type=FieldType.STRING)
    text = Indexer._prepare_text_for_embedding(field)
    assert text == "description: Test value"


# ---------------------------------------------------------------------------
# Record creation
# ---------------------------------------------------------------------------


def test_make_indexable_record_with_embedding_hash(indexer):
    """Test creating an indexable record that points at an embedding."""
    field = ExtractedField(path="description", value="Test value", value_type=FieldType.STRING)

    record = indexer._make_indexable_record(field, ENTITY_ID, "some-hash")

    assert record["entity_id"] == ENTITY_ID
    assert record["entity_type"] == EntityType.SUBSCRIPTION.value
    assert record["entity_title"] == ENTITY_TITLE
    assert record["path"] == Ltree("description")
    assert record["value"] == "Test value"
    assert record["value_type"] == FieldType.STRING
    assert record["embedding_hash"] == "some-hash"
    assert isinstance(record["content_hash"], str)
    assert len(record["content_hash"]) == 64


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------


def test_determine_changes_new_entity(indexer, mock_entity):
    """Test detecting changes for a new entity (no existing data)."""
    with patch.object(indexer, "_get_all_existing_hashes", return_value={}):
        fields_to_upsert, paths_to_delete, identical_count = indexer._determine_changes([mock_entity], session=None)

    assert len(fields_to_upsert) == 3
    assert len(paths_to_delete) == 0
    assert identical_count == 0


def test_determine_changes_identical_entity(indexer, mock_entity, matching_hashes):
    """Test detecting no changes when entity is identical."""
    with patch.object(indexer, "_get_all_existing_hashes", return_value=matching_hashes):
        fields_to_upsert, paths_to_delete, identical_count = indexer._determine_changes([mock_entity], session=None)

    assert len(fields_to_upsert) == 0
    assert len(paths_to_delete) == 0
    assert identical_count == 3


# ---------------------------------------------------------------------------
# Force index
# ---------------------------------------------------------------------------


def test_force_index_ignores_existing_hashes(mock_config, mock_entity):
    """Test that force_index=True reindexes all fields."""
    force_indexer = Indexer(config=mock_config, dry_run=True, force_index=True, chunk_size=10)
    force_indexer._entity_titles[ENTITY_ID] = ENTITY_TITLE

    existing_hashes = {
        ENTITY_ID: {
            "description": StoredHashes(
                Indexer._compute_content_hash("description", "Test subscription", FieldType.STRING, ENTITY_TITLE), None
            ),
            "status": StoredHashes(
                Indexer._compute_content_hash("status", "active", FieldType.STRING, ENTITY_TITLE), None
            ),
            "insync": StoredHashes(
                Indexer._compute_content_hash("insync", "true", FieldType.BOOLEAN, ENTITY_TITLE), None
            ),
        }
    }

    with patch.object(force_indexer, "_get_all_existing_hashes", return_value=existing_hashes):
        fields_to_upsert, paths_to_delete, identical_count = force_indexer._determine_changes(
            [mock_entity], session=None
        )

    assert len(fields_to_upsert) == 3
    assert identical_count == 0


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------


def test_get_max_tokens_from_model(indexer):
    """Test retrieving max tokens from model."""
    with patch("litellm.utils.get_max_tokens", return_value=8191):
        assert indexer._get_max_tokens() == 8191


def test_get_max_tokens_fallback(indexer):
    """Test fallback when model is not recognized."""
    with (
        patch("litellm.utils.get_max_tokens", side_effect=Exception("Unknown model")),
        patch("orchestrator.core.search.indexing.indexer.llm_settings.EMBEDDING_FALLBACK_MAX_TOKENS", 8000),
    ):
        assert indexer._get_max_tokens() == 8000


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


def test_dry_run_no_database_writes(mock_config, mock_entity):
    """Test that dry run doesn't execute database operations."""
    idx = Indexer(config=mock_config, dry_run=True, force_index=False, chunk_size=10)

    with (
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            return_value=[[0.1, 0.2], [0.3, 0.4]],
        ),
        patch(
            "orchestrator.core.search.indexing.indexer.Indexer._get_all_existing_hashes",
            return_value={},
        ),
    ):
        records_processed = idx.run([mock_entity])

    assert records_processed > 0


# ---------------------------------------------------------------------------
# Batch generation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field_path", "field_value", "field_type"),
    [
        pytest.param("description", "Short text", FieldType.STRING, id="embeddable"),
        pytest.param("insync", "false", FieldType.BOOLEAN, id="non_embeddable"),
    ],
)
def test_generate_upsert_batches(indexer, field_path, field_value, field_type):
    """Test batch generation for embeddable and non-embeddable fields."""
    fields_to_upsert = [
        (ENTITY_ID, ExtractedField(path=field_path, value=field_value, value_type=field_type)),
    ]

    should_have_embedding = field_type.is_embeddable(field_value)

    if should_have_embedding:
        with (
            patch("litellm.utils.encode", return_value=[1, 2, 3, 4, 5]),
            patch(
                "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
                return_value=[[0.1, 0.2]],
            ),
        ):
            batches = list(indexer._generate_upsert_batches(fields_to_upsert))
    else:
        batches = list(indexer._generate_upsert_batches(fields_to_upsert))

    assert len(batches) == 1
    assert len(batches[0].records) == 1
    assert (batches[0].records[0]["embedding_hash"] is not None) == should_have_embedding
    assert len(batches[0].embeddings) == should_have_embedding


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_tokenization_failure_skips_field(indexer):
    """Test that tokenization failures skip the field gracefully."""
    fields_to_upsert = [
        (ENTITY_ID, ExtractedField(path="description", value="Text", value_type=FieldType.STRING)),
    ]

    with patch("litellm.utils.encode", side_effect=Exception("Tokenization error")):
        batches = list(indexer._generate_upsert_batches(fields_to_upsert))

    assert batches == []


def test_field_exceeds_context_window(indexer):
    """Test that fields exceeding context window are skipped."""
    fields_to_upsert = [
        (ENTITY_ID, ExtractedField(path="description", value="Very long text" * 1000, value_type=FieldType.STRING)),
    ]

    with (
        patch("litellm.utils.encode", return_value=[1] * 10000),
        patch.object(indexer, "_get_max_tokens", return_value=8191),
    ):
        batches = list(indexer._generate_upsert_batches(fields_to_upsert))

    assert batches == []


_MISMATCH_PENDING = {"hash-1": "description: Text 1", "hash-2": "title: Text 2"}


def test_embedding_count_mismatch_raises_error(indexer):
    """Test that embedding count mismatch raises an error."""
    with (
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            return_value=[[0.1]],
        ),
        pytest.raises(ValueError, match="Embedding mismatch"),
    ):
        indexer._flush_buffer(_MISMATCH_PENDING, [])


# ---------------------------------------------------------------------------
# Embeddings in the database
# ---------------------------------------------------------------------------

ENTITY_UUIDS = [UUID(f"00000000-0000-0000-0000-00000000000{i}") for i in range(1, 4)]


def _vector(text: str) -> list[float]:
    return [float(len(text))] + [0.0] * (llm_settings.EMBEDDING_DIMENSION - 1)


def _working_api(texts: list[str], dry_run: bool) -> list[list[float]]:
    return [_vector(text) for text in texts]


def _failing_api(texts: list[str], dry_run: bool) -> list[list[float]]:
    return [[] for _ in texts]


@pytest.fixture
def api_enabled():
    with patch.object(llm_settings, "EMBEDDING_API_ENABLED", True):
        yield


@pytest.fixture
def embedding_api():
    """Stub litellm tokenization and the embedding API, which works until a test swaps its side effect."""
    with (
        patch("litellm.utils.get_max_tokens", return_value=8191),
        patch("litellm.utils.encode", return_value=[1]),
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            side_effect=_working_api,
        ) as api,
    ):
        yield api


def _index(
    fields: list[ExtractedField],
    title: str = ENTITY_TITLE,
    entity_ids: list[UUID] = ENTITY_UUIDS,
    cleanup_orphans: bool = False,
) -> int:
    """Index the same fields for each entity, for real, in the test database."""
    config = MagicMock()
    config.entity_kind = EntityType.SUBSCRIPTION
    config.pk_name = "entity_id"
    config.root_name = "subscription"
    config.traverser.get_fields.return_value = fields
    config.get_title_from_fields.return_value = title
    entities = [SimpleNamespace(entity_id=entity_id) for entity_id in entity_ids]
    indexer = Indexer(config=config, dry_run=False, force_index=False, chunk_size=10, cleanup_orphans=cleanup_orphans)
    return indexer.run(entities)  # type: ignore[arg-type]


def _stored_embedding_hashes() -> set[str]:
    return set(db.session.scalars(select(AiSearchEmbedding.embedding_hash)))


def _index_rows() -> list[AiSearchIndex]:
    return list(db.session.scalars(select(AiSearchIndex).order_by(AiSearchIndex.entity_id, AiSearchIndex.path)))


def _sent_texts(api: MagicMock) -> list[str]:
    return [text for call in api.call_args_list for text in call.args[0]]


_TEXT_FIELDS = [
    ExtractedField(path="description", value="Alpha", value_type=FieldType.STRING),
    ExtractedField(path="name", value="Beta", value_type=FieldType.STRING),
    ExtractedField(path="insync", value="true", value_type=FieldType.BOOLEAN),
]


@pytest.mark.usefixtures("api_enabled")
def test_title_change_embeds_nothing(embedding_api):
    _index(_TEXT_FIELDS, title="Old title")
    old_content_hashes = {row.content_hash for row in _index_rows()}
    embedding_api.reset_mock()

    processed = _index(_TEXT_FIELDS, title="New title")

    embedding_api.assert_not_called()
    assert processed == 9
    rows = _index_rows()
    assert {row.entity_title for row in rows} == {"New title"}
    assert {row.content_hash for row in rows}.isdisjoint(old_content_hashes)
    assert len(_stored_embedding_hashes()) == 2


@pytest.mark.usefixtures("api_enabled")
def test_model_switch_reembeds_distinct_texts_once(embedding_api):
    _index(_TEXT_FIELDS)
    hashes_before = {row.embedding_hash for row in _index_rows()} - {None}

    embedding_api.reset_mock()
    with patch.object(llm_settings, "EMBEDDING_MODEL", "another/embedding-model"):
        processed = _index(_TEXT_FIELDS)

    assert sorted(_sent_texts(embedding_api)) == ["description: Alpha", "name: Beta"]
    assert processed == 6
    hashes_after = {row.embedding_hash for row in _index_rows()} - {None}
    assert len(hashes_after) == 2
    assert hashes_after.isdisjoint(hashes_before)
    assert hashes_after <= _stored_embedding_hashes()


@pytest.mark.usefixtures("api_enabled")
def test_failed_batch_retried(embedding_api):
    embedding_api.side_effect = _failing_api
    assert _index(_TEXT_FIELDS) == 9

    failed_rows = _index_rows()
    assert {row.embedding_hash is None for row in failed_rows if row.path != Ltree("insync")} == {False}
    assert _stored_embedding_hashes() == set()

    embedding_api.reset_mock()
    embedding_api.side_effect = _working_api
    assert _index(_TEXT_FIELDS) == 6

    assert sorted(_sent_texts(embedding_api)) == ["description: Alpha", "name: Beta"]
    assert len(_stored_embedding_hashes()) == 2
    assert {row.embedding_hash for row in _index_rows() if row.path != Ltree("insync")} == _stored_embedding_hashes()

    embedding_api.reset_mock()
    assert _index(_TEXT_FIELDS) == 0
    embedding_api.assert_not_called()


@pytest.mark.usefixtures("api_enabled")
def test_partial_failure_only_embeds_missing(embedding_api):
    embedding_api.side_effect = lambda texts, dry_run: [[] if text == "name: Beta" else _vector(text) for text in texts]
    _index(_TEXT_FIELDS)
    assert len(_stored_embedding_hashes()) == 1

    embedding_api.reset_mock()
    embedding_api.side_effect = _working_api
    processed = _index(_TEXT_FIELDS)

    assert _sent_texts(embedding_api) == ["name: Beta"]
    assert processed == 3  # only the rows of the text that was missing
    assert len(_stored_embedding_hashes()) == 2


def test_api_disabled_second_run_changes_nothing(embedding_api):
    # The real API call answers with empty vectors when the API is disabled.
    embedding_api.side_effect = _failing_api
    with patch.object(llm_settings, "EMBEDDING_API_ENABLED", False):
        assert _index(_TEXT_FIELDS) == 9
        assert _stored_embedding_hashes() == set()

        assert _index(_TEXT_FIELDS) == 0

    assert {row.embedding_hash is None for row in _index_rows()} == {False, True}


def _seed_embedding(entity_type: EntityType, embedding_hash: str) -> None:
    db.session.add(
        AiSearchEmbedding(
            entity_type=entity_type.value, embedding_hash=embedding_hash, embedding=_vector(embedding_hash)
        )
    )
    db.session.commit()


def _stored_embedding_keys() -> set[tuple[str, str]]:
    return {
        (entity_type, embedding_hash)
        for entity_type, embedding_hash in db.session.execute(
            select(AiSearchEmbedding.entity_type, AiSearchEmbedding.embedding_hash)
        )
    }


@pytest.mark.usefixtures("api_enabled")
def test_orphans_deleted_for_indexed_type_only(embedding_api):
    _index(_TEXT_FIELDS)
    referenced = _stored_embedding_hashes()
    _seed_embedding(EntityType.SUBSCRIPTION, "orphan-subscription")
    _seed_embedding(EntityType.PRODUCT, "orphan-product")

    _index(_TEXT_FIELDS, cleanup_orphans=True)

    assert _stored_embedding_keys() == {(EntityType.SUBSCRIPTION.value, h) for h in referenced} | {
        (EntityType.PRODUCT.value, "orphan-product")
    }


@pytest.mark.usefixtures("api_enabled")
def test_run_without_cleanup_keeps_orphans(embedding_api):
    _seed_embedding(EntityType.SUBSCRIPTION, "orphan-subscription")

    _index(_TEXT_FIELDS, entity_ids=ENTITY_UUIDS[:1])

    assert (EntityType.SUBSCRIPTION.value, "orphan-subscription") in _stored_embedding_keys()


@pytest.mark.usefixtures("api_enabled")
def test_dry_run_deletes_nothing(embedding_api):
    _seed_embedding(EntityType.SUBSCRIPTION, "orphan-subscription")
    config = MagicMock()
    config.entity_kind = EntityType.SUBSCRIPTION

    Indexer(config=config, dry_run=True, force_index=False, chunk_size=10, cleanup_orphans=True).run([])

    assert _stored_embedding_keys() == {(EntityType.SUBSCRIPTION.value, "orphan-subscription")}
