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

"""Integration tests for the database reads and deletes behind the search CLI commands."""

from functools import partial
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.cli.search.display import display_filtered_paths_only, display_results
from orchestrator.core.cli.search.resize_embedding import (
    ENTITY_TYPES,
    alter_embedding_column_dimension,
    drop_all_embeddings,
    get_current_embedding_dimension,
    rebuild_hnsw_indexes,
)
from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchEmbedding, AiSearchIndex, SearchQueryTable
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.query.results import SearchResult
from orchestrator.core.settings import llm_settings
from test.integration_tests.search._embeddings import add_indexed_row


def _add_index_row(entity_id: UUID, path: str, value: str) -> None:
    db.session.add(
        AiSearchIndex(
            entity_type=EntityType.SUBSCRIPTION,
            entity_id=entity_id,
            path=Ltree(path),
            value=value,
            content_hash="0" * 64,
            value_type=FieldType.STRING,
        )
    )
    db.session.flush()


def _result(entity_id: UUID) -> SearchResult:
    return SearchResult(entity_id=str(entity_id), entity_type=EntityType.SUBSCRIPTION, entity_title="title", score=1.0)


def test_display_filtered_paths_only_logs_value_for_searched_path():
    entity_id = uuid4()
    _add_index_row(entity_id, "subscription.description", "matched value")
    _add_index_row(entity_id, "subscription.status", "other value")
    query = MagicMock()
    query.filters.get_all_paths.return_value = ["subscription.description"]

    with patch("orchestrator.core.cli.search.display.logger") as logger:
        display_filtered_paths_only([_result(entity_id)], query, db.session)

    logged = [c.args[0] for c in logger.info.call_args_list]
    assert "  subscription.description: matched value" in logged
    assert not any("other value" in line for line in logged)


def test_display_results_warns_when_entity_has_no_index_rows():
    entity_id = uuid4()

    with patch("orchestrator.core.cli.search.display.logger") as logger:
        display_results([_result(entity_id)], db.session)

    logger.warning.assert_called_once_with(f"Could not find indexed records for entity_id={entity_id}")


def test_display_results_warns_when_indexed_entity_is_gone():
    entity_id = uuid4()
    _add_index_row(entity_id, "subscription.description", "orphaned")

    with patch("orchestrator.core.cli.search.display.logger") as logger:
        display_results([_result(entity_id)], db.session)

    logger.warning.assert_called_once_with(f"Could not display entity SUBSCRIPTION with id={entity_id}")


def _row_counts() -> list[int]:
    return [
        db.session.execute(select(func.count()).select_from(table)).scalar_one()
        for table in (AiSearchIndex, AiSearchEmbedding, SearchQueryTable)
    ]


def test_drop_all_embeddings_empties_every_table():
    add_embedded_row = partial(
        add_indexed_row,
        db.session,
        entity_type=EntityType.SUBSCRIPTION,
        path="subscription.description",
        value="a",
        embedding=[1.0] + [0.0] * (llm_settings.EMBEDDING_DIMENSION - 1),
    )
    add_embedded_row(entity_id=uuid4())
    add_embedded_row(entity_id=uuid4())  # same text, so both rows share one embeddings row
    db.session.add(SearchQueryTable(query_number=1, parameters={}))
    db.session.flush()
    assert _row_counts() == [2, 1, 1]

    index_deleted, query_deleted = drop_all_embeddings()

    assert (index_deleted, query_deleted) == (2, 1)
    assert _row_counts() == [0, 0, 0]


def _vector_dimension(table: str, column: str) -> int:
    return db.session.execute(
        text("SELECT atttypmod FROM pg_attribute WHERE attrelid = CAST(:table AS regclass) AND attname = :column"),
        {"table": table, "column": column},
    ).scalar_one()


def test_current_dimension_comes_from_the_column_not_from_stored_rows():
    try:
        db.session.execute(delete(AiSearchEmbedding))

        assert get_current_embedding_dimension() == llm_settings.EMBEDDING_DIMENSION
    finally:
        db.session.rollback()


def test_current_dimension_is_none_when_the_column_or_table_is_missing():
    try:
        db.session.execute(text("ALTER TABLE ai_search_embeddings RENAME COLUMN embedding TO embedding_gone"))
        assert get_current_embedding_dimension() is None

        db.session.execute(text("ALTER TABLE ai_search_embeddings RENAME TO ai_search_embeddings_gone"))
        assert get_current_embedding_dimension() is None
    finally:
        db.session.rollback()


def test_resize_rebuilds_embeddings_table():
    new_dimension = llm_settings.EMBEDDING_DIMENSION + 1
    try:
        drop_all_embeddings()
        alter_embedding_column_dimension(new_dimension)
        rebuild_hnsw_indexes()

        assert _vector_dimension("ai_search_embeddings", "embedding") == new_dimension
        assert _vector_dimension("search_queries", "query_embedding") == new_dimension
        assert get_current_embedding_dimension() == new_dimension
        inspector = inspect(db.session.connection())
        assert {index["name"] for index in inspector.get_indexes("ai_search_embeddings")} >= {
            f"ix_ai_search_embeddings_hnsw_{entity_type.lower()}" for entity_type in ENTITY_TYPES
        }
        assert "embedding" not in {column["name"] for column in inspector.get_columns("ai_search_index")}
    finally:
        alter_embedding_column_dimension(llm_settings.EMBEDDING_DIMENSION)
        rebuild_hnsw_indexes()
