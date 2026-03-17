# Copyright 2019-2025 SURF, GÉANT.
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


from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.search.core.types import EntityType, ExtractedField, FieldType
from orchestrator.search.indexing.indexer import Indexer

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
    indexer = Indexer(config=mock_config, dry_run=True, force_index=False, chunk_size=10)
    indexer._entity_titles[ENTITY_ID] = ENTITY_TITLE
    return indexer


class TestIndexerContentHashing:
    """Test content hashing functionality."""

    @pytest.mark.parametrize(
        "path1,value1,path2,value2,should_match",
        [
            ("path", "value", "path", "value", True),  # Deterministic - same inputs
            ("path", "value1", "path", "value2", False),  # Different values
            ("path1", "value", "path2", "value", False),  # Different paths
            ("path", None, "path", None, True),  # None values deterministic
        ],
    )
    def test_compute_content_hash(self, path1, value1, path2, value2, should_match):
        """Test content hash is deterministic and sensitive to path/value changes."""
        hash1 = Indexer._compute_content_hash(path1, value1, FieldType.STRING, "title")
        hash2 = Indexer._compute_content_hash(path2, value2, FieldType.STRING, "title")

        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256

        if should_match:
            assert hash1 == hash2
        else:
            assert hash1 != hash2


class TestIndexerTextPreparation:
    """Test text preparation for embeddings."""

    def test_prepare_text_for_embedding(self):
        """Test text preparation combines path and value."""
        field = ExtractedField(path="description", value="Test value", value_type=FieldType.STRING)
        text = Indexer._prepare_text_for_embedding(field)
        assert text == "description: Test value"


class TestIndexerRecordCreation:
    """Test creation of indexable records."""

    def test_make_indexable_record_with_embedding(self, indexer):
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


class TestIndexerDetermineChanges:
    """Test change detection logic."""

    @pytest.fixture
    def matching_hashes(self, mock_fields):
        """Hashes that match mock_entity fields."""
        return {
            ENTITY_ID: {
                field.path: Indexer._compute_content_hash(field.path, field.value, field.value_type, ENTITY_TITLE)
                for field in mock_fields
            }
        }

    def test_determine_changes_new_entity(self, indexer, mock_entity):
        """Test detecting changes for a new entity (no existing data)."""
        with patch.object(indexer, "_get_all_existing_hashes", return_value={}):
            fields_to_upsert, paths_to_delete, identical_count = indexer._determine_changes([mock_entity], session=None)

        assert len(fields_to_upsert) == 3
        assert len(paths_to_delete) == 0
        assert identical_count == 0

    def test_determine_changes_identical_entity(self, indexer, mock_entity, matching_hashes):
        """Test detecting no changes when entity is identical."""
        with patch.object(indexer, "_get_all_existing_hashes", return_value=matching_hashes):
            fields_to_upsert, paths_to_delete, identical_count = indexer._determine_changes([mock_entity], session=None)

        assert len(fields_to_upsert) == 0
        assert len(paths_to_delete) == 0
        assert identical_count == 3


class TestIndexerForceIndex:
    """Test force index functionality."""

    def test_force_index_ignores_existing_hashes(self, mock_config, mock_entity):
        """Test that force_index=True reindexes all fields."""
        force_indexer = Indexer(config=mock_config, dry_run=True, force_index=True, chunk_size=10)
        force_indexer._entity_titles[ENTITY_ID] = ENTITY_TITLE

        # Mock existing hashes that match current content
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


class TestIndexerTokenCounting:
    """Test token counting and batching logic."""

    def test_get_max_tokens_from_model(self, indexer):
        """Test retrieving max tokens from model."""
        with patch("orchestrator.search.indexing.indexer.get_max_tokens", return_value=8191):
            assert indexer._get_max_tokens() == 8191

    def test_get_max_tokens_fallback(self, indexer):
        """Test fallback when model is not recognized."""
        with (
            patch("orchestrator.search.indexing.indexer.get_max_tokens", side_effect=Exception("Unknown model")),
            patch("orchestrator.search.indexing.indexer.llm_settings.EMBEDDING_FALLBACK_MAX_TOKENS", 8000),
        ):
            assert indexer._get_max_tokens() == 8000


class TestIndexerDryRun:
    """Test dry run functionality."""

    def test_dry_run_no_database_writes(self, mock_config, mock_entity):
        """Test that dry run doesn't execute database operations."""
        indexer = Indexer(config=mock_config, dry_run=True, force_index=False, chunk_size=10)

        # Return 2 embeddings (one for "description" and one for "status")
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
            # This should not raise an error even without a real database session
            records_processed = indexer.run([mock_entity])

        # Should still count records as processed
        assert records_processed > 0


class TestIndexerBatchGeneration:
    """Test batch generation for upserts."""

    @pytest.mark.parametrize(
        "field_path,field_value,field_type",
        [
            ("description", "Short text", FieldType.STRING),  # Embeddable field
            ("insync", "false", FieldType.BOOLEAN),  # Non-embeddable field
        ],
    )
    def test_generate_upsert_batches(self, indexer, field_path, field_value, field_type):
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


class TestIndexerErrorHandling:
    """Test error handling in indexer."""

    def test_tokenization_failure_skips_field(self, indexer):
        """Test that tokenization failures skip the field gracefully."""
        fields_to_upsert = [
            (ENTITY_ID, ExtractedField(path="description", value="Text", value_type=FieldType.STRING)),
        ]

        with patch("orchestrator.search.indexing.indexer.encode", side_effect=Exception("Tokenization error")):
            batches = list(indexer._generate_upsert_batches(fields_to_upsert))

        assert batches == []

    def test_field_exceeds_context_window(self, indexer):
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

    def test_embedding_count_mismatch_raises_error(self, indexer):
        """Test that embedding count mismatch raises an error."""
        embeddable_buffer = [
            (ENTITY_ID, ExtractedField(path="description", value="Text 1", value_type=FieldType.STRING)),
            (ENTITY_ID, ExtractedField(path="title", value="Text 2", value_type=FieldType.STRING)),
        ]

        with (
            patch(
                "orchestrator.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
                return_value=[[0.1]],
            ),
            pytest.raises(ValueError, match="Embedding mismatch"),
        ):
            indexer._flush_buffer(embeddable_buffer, [])
