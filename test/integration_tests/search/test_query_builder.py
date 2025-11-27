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

import pytest

from orchestrator.db import db
from orchestrator.search.aggregations import AggregationType, CountAggregation
from orchestrator.search.core.types import BooleanOperator, EntityType, FilterOp, UIType
from orchestrator.search.filters import EqualityFilter, FilterTree, PathFilter
from orchestrator.search.query import engine
from orchestrator.search.query.queries import AggregateQuery, CountQuery, ExportQuery, SelectQuery
from orchestrator.types import SubscriptionLifecycle

FILTER_STATUS_ACTIVE = PathFilter(
    path="status",
    condition=EqualityFilter(op=FilterOp.EQ, value="active"),
    value_kind=UIType.STRING,
)

FILTER_STATUS_PROVISIONING = PathFilter(
    path="status",
    condition=EqualityFilter(op=FilterOp.EQ, value="provisioning"),
    value_kind=UIType.STRING,
)

FILTER_INSYNC_TRUE = PathFilter(
    path="insync",
    condition=EqualityFilter(op=FilterOp.EQ, value=True),
    value_kind=UIType.BOOLEAN,
)


class TestCandidateQueryBuilder:
    """Test build_candidate_query SQL generation with filters."""

    @pytest.mark.asyncio
    async def test_complex_filter_and_logic(self, indexed_subscriptions, mock_embeddings):
        """Test AND logic with multiple filters executes correctly."""
        query = SelectQuery(
            entity_type=EntityType.SUBSCRIPTION,
            filters=FilterTree(
                op=BooleanOperator.AND,
                children=[FILTER_STATUS_ACTIVE, FILTER_INSYNC_TRUE],
            ),
            limit=30,
        )

        response = await engine.execute_search(query, db.session)

        # 21 subscriptions have both status=active AND insync=true
        assert len(response.results) == 21, f"Should return 21 results, got {len(response.results)}"

    @pytest.mark.asyncio
    async def test_complex_filter_or_logic(self, indexed_subscriptions, mock_embeddings):
        """Test OR logic with multiple filters executes correctly."""
        query = SelectQuery(
            entity_type=EntityType.SUBSCRIPTION,
            filters=FilterTree(
                op=BooleanOperator.OR,
                children=[FILTER_STATUS_ACTIVE, FILTER_STATUS_PROVISIONING],
            ),
            limit=30,
        )

        response = await engine.execute_search(query, db.session)

        # 21 active + 1 provisioning = 22 total
        assert len(response.results) == 22, f"Should return 22 results, got {len(response.results)}"

    @pytest.mark.asyncio
    async def test_nested_filter_logic(self, indexed_subscriptions, mock_embeddings):
        """Test nested AND/OR filter combinations execute correctly."""
        query = SelectQuery(
            entity_type=EntityType.SUBSCRIPTION,
            filters=FilterTree(
                op=BooleanOperator.AND,
                children=[
                    FILTER_INSYNC_TRUE,
                    FilterTree(
                        op=BooleanOperator.OR,
                        children=[FILTER_STATUS_ACTIVE, FILTER_STATUS_PROVISIONING],
                    ),
                ],
            ),
            limit=30,
        )

        response = await engine.execute_search(query, db.session)

        # insync=true AND (active OR provisioning) = 21 (all insync=true are active)
        assert len(response.results) == 21, f"Should return 21 results, got {len(response.results)}"


class TestAggregationQueryBuilder:
    """Test build_aggregation_query SQL generation."""

    @pytest.mark.asyncio
    async def test_simple_count_no_grouping(self, indexed_subscriptions):
        """Test simple COUNT query without grouping."""
        query = CountQuery(
            entity_type=EntityType.SUBSCRIPTION,
        )

        response = await engine.execute_aggregation(query, db.session)

        assert len(response.results) == 1, "Should have single result for simple count"
        assert response.results[0].aggregations["total_count"] == 22, "Should count all 22 subscriptions"

    @pytest.mark.asyncio
    async def test_count_with_grouping(self, indexed_subscriptions):
        """Test COUNT query with GROUP BY."""
        query = CountQuery(
            entity_type=EntityType.SUBSCRIPTION,
            group_by=["status"],
        )

        response = await engine.execute_aggregation(query, db.session)

        assert len(response.results) == 2, "Should have 2 status groups"
        assert response.total_groups == 2, "Should report 2 total groups"

        # Verify exact counts for each status
        results_by_status = {g.group_values["status"]: g.aggregations["count"] for g in response.results}
        assert results_by_status[SubscriptionLifecycle.ACTIVE.value] == 21, "Should have 21 active"
        assert results_by_status[SubscriptionLifecycle.PROVISIONING.value] == 1, "Should have 1 provisioning"

    @pytest.mark.asyncio
    async def test_aggregate_with_multiple_aggregations(self, indexed_subscriptions):
        """Test AGGREGATE query with multiple aggregations."""
        query = AggregateQuery(
            entity_type=EntityType.SUBSCRIPTION,
            group_by=["status"],
            aggregations=[
                CountAggregation(type=AggregationType.COUNT, alias="count"),
            ],
        )

        response = await engine.execute_aggregation(query, db.session)

        assert len(response.results) == 2, "Should have 2 status groups"

        # Verify exact aggregation values
        results_by_status = {g.group_values["status"]: g.aggregations for g in response.results}
        assert results_by_status[SubscriptionLifecycle.ACTIVE.value]["count"] == 21
        assert results_by_status[SubscriptionLifecycle.PROVISIONING.value]["count"] == 1

    @pytest.mark.asyncio
    async def test_count_with_filters(self, indexed_subscriptions):
        """Test COUNT query with filters applied."""
        query = CountQuery(
            entity_type=EntityType.SUBSCRIPTION,
            filters=FilterTree(
                op=BooleanOperator.AND,
                children=[FILTER_STATUS_ACTIVE],
            ),
            group_by=["insync"],
        )

        response = await engine.execute_aggregation(query, db.session)

        # Only active subscriptions, all 21 have insync=true
        assert len(response.results) == 1, "Should have 1 insync group (all active are insync=true)"
        assert response.results[0].group_values["insync"] == "true"
        assert response.results[0].aggregations["count"] == 21


class TestExportQueryBuilder:
    """Test export query execution with filters."""

    @pytest.mark.asyncio
    async def test_export_with_filters(self, indexed_subscriptions, mock_embeddings):
        """Test EXPORT query with filters fetches flattened data."""
        query = ExportQuery(
            entity_type=EntityType.SUBSCRIPTION,
            filters=FilterTree(
                op=BooleanOperator.AND,
                children=[FILTER_STATUS_ACTIVE],
            ),
            limit=30,
        )

        export_data = await engine.execute_export(query, db.session)

        # Should export all 21 active subscriptions
        assert len(export_data) == 21, f"Should export 21 active subscriptions, got {len(export_data)}"

        # Verify all exported records are active
        assert all(record["status"] == SubscriptionLifecycle.ACTIVE.value for record in export_data)
