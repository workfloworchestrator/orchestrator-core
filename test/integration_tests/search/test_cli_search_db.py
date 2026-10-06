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

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.cli.search.display import display_filtered_paths_only, display_results
from orchestrator.core.cli.search.resize_embedding import drop_all_embeddings
from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.query.results import SearchResult


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


def test_drop_all_embeddings_returns_deleted_counts():
    _add_index_row(uuid4(), "subscription.description", "a")
    _add_index_row(uuid4(), "subscription.description", "b")

    index_deleted, query_deleted = drop_all_embeddings()

    assert (index_deleted, query_deleted) == (2, 0)
    assert db.session.scalar(select(func.count()).select_from(AiSearchIndex)) == 0
