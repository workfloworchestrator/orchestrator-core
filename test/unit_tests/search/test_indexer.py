"""Tests for Indexer public API.

Content hashing, text preparation, record creation, change detection,
force index, token counting, dry run, batch generation, and error handling.
"""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.search.core.types import EntityType, ExtractedField, FieldType
from orchestrator.core.search.indexing.indexer import Indexer

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
            field.path: Indexer._compute_content_hash(field.path, field.value, field.value_type, ENTITY_TITLE)
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


def test_make_indexable_record_with_embedding(indexer):
    """Test creating an indexable record with embedding."""
    field = ExtractedField(path="description", value="Test value", value_type=FieldType.STRING)
    embedding = [0.1, 0.2, 0.3]

    record = indexer._make_indexable_record(field, ENTITY_ID, embedding)

    assert record["entity_id"] == ENTITY_ID
    assert record["entity_type"] == EntityType.SUBSCRIPTION.value
    assert record["entity_title"] == ENTITY_TITLE
    assert record["path"] == Ltree("description")
    assert record["value"] == "Test value"
    assert record["value_type"] == FieldType.STRING
    assert record["embedding"] == embedding
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
            "description": Indexer._compute_content_hash(
                "description", "Test subscription", FieldType.STRING, ENTITY_TITLE
            ),
            "status": Indexer._compute_content_hash("status", "active", FieldType.STRING, ENTITY_TITLE),
            "insync": Indexer._compute_content_hash("insync", "true", FieldType.BOOLEAN, ENTITY_TITLE),
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
    with patch("orchestrator.search.indexing.indexer.get_max_tokens", return_value=8191):
        assert indexer._get_max_tokens() == 8191


def test_get_max_tokens_fallback(indexer):
    """Test fallback when model is not recognized."""
    with (
        patch("orchestrator.search.indexing.indexer.get_max_tokens", side_effect=Exception("Unknown model")),
        patch("orchestrator.search.indexing.indexer.llm_settings.EMBEDDING_FALLBACK_MAX_TOKENS", 8000),
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
            "orchestrator.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            return_value=[[0.1, 0.2], [0.3, 0.4]],
        ),
        patch(
            "orchestrator.search.indexing.indexer.Indexer._get_all_existing_hashes",
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
            patch("orchestrator.search.indexing.indexer.encode", return_value=[1, 2, 3, 4, 5]),
            patch(
                "orchestrator.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
                return_value=[[0.1, 0.2]],
            ),
        ):
            batches = list(indexer._generate_upsert_batches(fields_to_upsert))
    else:
        batches = list(indexer._generate_upsert_batches(fields_to_upsert))

    assert len(batches) == 1
    assert len(batches[0]) == 1
    assert (batches[0][0]["embedding"] is not None) == should_have_embedding


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_tokenization_failure_skips_field(indexer):
    """Test that tokenization failures skip the field gracefully."""
    fields_to_upsert = [
        (ENTITY_ID, ExtractedField(path="description", value="Text", value_type=FieldType.STRING)),
    ]

    with patch("orchestrator.search.indexing.indexer.encode", side_effect=Exception("Tokenization error")):
        batches = list(indexer._generate_upsert_batches(fields_to_upsert))

    assert batches == []


def test_field_exceeds_context_window(indexer):
    """Test that fields exceeding context window are skipped."""
    fields_to_upsert = [
        (ENTITY_ID, ExtractedField(path="description", value="Very long text" * 1000, value_type=FieldType.STRING)),
    ]

    with (
        patch("orchestrator.search.indexing.indexer.encode", return_value=[1] * 10000),
        patch.object(indexer, "_get_max_tokens", return_value=8191),
    ):
        batches = list(indexer._generate_upsert_batches(fields_to_upsert))

    assert batches == []


_MISMATCH_BUFFER = [
    (ENTITY_ID, ExtractedField(path="description", value="Text 1", value_type=FieldType.STRING)),
    (ENTITY_ID, ExtractedField(path="title", value="Text 2", value_type=FieldType.STRING)),
]


def test_embedding_count_mismatch_raises_error(indexer):
    """Test that embedding count mismatch raises an error."""
    with (
        patch(
            "orchestrator.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            return_value=[[0.1]],
        ),
        pytest.raises(ValueError, match="Embedding mismatch"),
    ):
        indexer._flush_buffer(_MISMATCH_BUFFER, [])
