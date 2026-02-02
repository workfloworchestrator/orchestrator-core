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

from unittest.mock import patch
from uuid import UUID

import pytest

from orchestrator.db import db
from orchestrator.search.core.types import BooleanOperator, EntityType, FilterOp, SearchMetadata, UIType
from orchestrator.search.filters import EqualityFilter, FilterTree, PathFilter
from orchestrator.search.query import engine
from orchestrator.search.query.queries import SelectQuery
from orchestrator.search.retrieval.pagination import PageCursor
from orchestrator.types import SubscriptionLifecycle

from .fixtures import (
    PANCAKES_ID,
    QUERY_ASIAN_CUISINE,
    QUERY_BREAKFAST_SYRUP,
    QUERY_CHEESE_PIZZA,
    QUERY_CHOCOLATE,
    QUERY_CHOCOLATE_DESSERT,
    QUERY_ITALIAN,
    QUERY_PANCAKES,
    QUERY_SALMON_LEMON,
    QUERY_SPICY_ITALIAN,
    QUERY_VEGETARIAN_MEALS,
    TEST_SUBSCRIPTIONS,
)
from .helpers import get_expected_ranking


class TestSemanticRetrieval:
    """Test semantic retrieval (multi-word queries use SemanticRetriever).

    All benchmark queries are multi-word, so fuzzy_term=None and they use SemanticRetriever.
    These tests validate rankings match ground truth.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query_text",
        [
            QUERY_SPICY_ITALIAN,
            QUERY_CHOCOLATE_DESSERT,
            QUERY_VEGETARIAN_MEALS,
            QUERY_BREAKFAST_SYRUP,
            QUERY_SALMON_LEMON,
            QUERY_CHEESE_PIZZA,
            QUERY_ASIAN_CUISINE,
        ],
    )
    async def test_ranking_matches_ground_truth(self, query_text, indexed_subscriptions, mock_embeddings):
        """Test that semantic search ranking matches ground truth for multi-word queries."""

        query = SelectQuery(
            entity_type=EntityType.SUBSCRIPTION,
            query_text=query_text,
            limit=10,
        )
        response = await engine.execute_search(query, db.session)

        # Verify semantic retriever was used (multi-word queries don't set fuzzy_term)
        assert (
            response.metadata == SearchMetadata.semantic()
        ), f"Expected semantic retriever for multi-word query, got {response.metadata.search_type}"

        result_ids = [str(r.entity_id) for r in response.results]
        expected_ranking = get_expected_ranking(query_text)

        assert result_ids == expected_ranking, (
            f"Ranking should match ground truth.\n" f"Expected: {expected_ranking}\n" f"Got: {result_ids}"
        )


class TestHybridRetrieval:
    """Test hybrid retrieval (single-word queries use HybridRetriever).

    Single-word queries set both vector_query and fuzzy_term, triggering HybridRetriever.
    These tests validate rankings match ground truth.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query_text",
        [
            QUERY_ITALIAN,
            QUERY_CHOCOLATE,
            QUERY_PANCAKES,
        ],
    )
    async def test_ranking_matches_ground_truth(self, query_text, indexed_subscriptions, mock_embeddings):
        """Test that hybrid search ranking matches ground truth for single-word queries."""

        query = SelectQuery(
            entity_type=EntityType.SUBSCRIPTION,
            query_text=query_text,
            limit=10,
        )
        response = await engine.execute_search(query, db.session)

        # Verify hybrid retriever was used (single-word queries use hybrid)
        assert (
            response.metadata == SearchMetadata.hybrid()
        ), f"Expected hybrid retriever for single-word query, got {response.metadata}"

        result_ids = [str(r.entity_id) for r in response.results]
        expected_ranking = get_expected_ranking(query_text)

        assert result_ids == expected_ranking, (
            f"Ranking should match ground truth.\n" f"Expected: {expected_ranking}\n" f"Got: {result_ids}"
        )


class TestFuzzyRetrieval:
    """Test fuzzy retrieval (text-only search without embeddings)."""

    @pytest.mark.asyncio
    async def test_fuzzy_only_when_embedding_fails(self, indexed_subscriptions):
        """Test that fuzzy retriever is used when embedding generation fails (returns None)."""
        query = SelectQuery(
            entity_type=EntityType.SUBSCRIPTION,
            query_text=QUERY_PANCAKES,
            limit=10,
        )

        # Mock embedding generation to return None (simulating failure)
        with patch("orchestrator.search.core.embedding.QueryEmbedder.generate_for_text_async", return_value=None):
            response = await engine.execute_search(query, db.session)

        # Verify fuzzy retriever was used when embedding generation failed
        assert (
            response.metadata == SearchMetadata.fuzzy()
        ), f"Expected fuzzy retriever when embedding=None, got {response.metadata}"

        # Should return pancakes result
        assert len(response.results) >= 1, f"Should return at least 1 subscription, got {len(response.results)}"

        result_ids = [UUID(r.entity_id) if isinstance(r.entity_id, str) else r.entity_id for r in response.results]
        assert result_ids[0] == PANCAKES_ID, f"Pancakes subscription should rank first, got {result_ids[0]}"


class TestStructuredRetrieval:
    """Test structured retrieval (filter-only queries use StructuredRetriever)."""

    @pytest.mark.asyncio
    async def test_filter_only_uses_structured_retriever(self, indexed_subscriptions, mock_embeddings):
        """Test that filter-only queries use structured retriever."""
        query = SelectQuery(
            entity_type=EntityType.SUBSCRIPTION,
            filters=FilterTree(
                op=BooleanOperator.AND,
                children=[
                    PathFilter(
                        path="status",
                        condition=EqualityFilter(op=FilterOp.EQ, value="active"),
                        value_kind=UIType.STRING,
                    )
                ],
            ),
            limit=10,
        )

        response = await engine.execute_search(query, db.session)

        # Verify structured retriever was used
        assert (
            response.metadata == SearchMetadata.structured()
        ), f"Expected structured retriever, got {response.metadata}"

        # Limited to 10 by query limit, but metadata should indicate more available
        assert len(response.results) == 10, f"Should return 10 results (limit), got {len(response.results)}"
        assert response.has_more is True, "Should indicate more results available"
        assert response.total_items == 21
        assert response.start_cursor == 0
        assert response.end_cursor == 9

        # Verify all results have status="active"
        result_ids = [UUID(r.entity_id) if isinstance(r.entity_id, str) else r.entity_id for r in response.results]
        test_subs_by_id = {sub["subscription_id"]: sub for sub in TEST_SUBSCRIPTIONS}

        assert all(
            test_subs_by_id[rid]["status"] == SubscriptionLifecycle.ACTIVE for rid in result_ids
        ), "All results should have status=active"

    @pytest.mark.asyncio
    async def test_filter_only_uses_structured_retriever_with_cursor(self, indexed_subscriptions, mock_embeddings):
        """Test that structured retriever with cursor correctly returns the total and start cursor."""

        query = SelectQuery(
            entity_type=EntityType.SUBSCRIPTION,
            filters=FilterTree(
                op=BooleanOperator.AND,
                children=[
                    PathFilter(
                        path="status",
                        condition=EqualityFilter(op=FilterOp.EQ, value="active"),
                        value_kind=UIType.STRING,
                    )
                ],
            ),
        )

        subscription_15_uuid: UUID = indexed_subscriptions[15].subscription_id  # type: ignore
        response = await engine.execute_search(
            query, db.session, cursor=PageCursor(score=0, id=str(subscription_15_uuid), query_id=subscription_15_uuid)
        )

        # Verify structured retriever was used
        assert (
            response.metadata == SearchMetadata.structured()
        ), f"Expected structured retriever, got {response.metadata}"

        assert len(response.results) == 5, f"Should return 5 results, got {len(response.results)}"
        assert response.has_more is False, "Should indicate no more results available"
        assert response.total_items == 21
        assert response.start_cursor == 16
        assert response.end_cursor == 20

    @pytest.mark.asyncio
    async def test_filter_only_uses_structured_retriever_with_no_results(self, indexed_subscriptions, mock_embeddings):
        """Test that structured retriever with cursor correctly returns the total and start cursor."""

        query = SelectQuery(
            entity_type=EntityType.SUBSCRIPTION,
            filters=FilterTree(
                op=BooleanOperator.AND,
                children=[
                    PathFilter(
                        path="status",
                        condition=EqualityFilter(op=FilterOp.EQ, value="no results"),
                        value_kind=UIType.STRING,
                    )
                ],
            ),
        )

        response = await engine.execute_search(query, db.session)

        # Verify structured retriever was used
        assert (
            response.metadata == SearchMetadata.structured()
        ), f"Expected structured retriever, got {response.metadata}"

        assert len(response.results) == 0
        assert response.has_more is False
        assert not response.total_items
        assert not response.start_cursor
        assert not response.end_cursor
