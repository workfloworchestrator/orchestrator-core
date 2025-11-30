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
from pydantic import ValidationError

from orchestrator.search.aggregations import (
    AggregationType,
    CountAggregation,
    FieldAggregation,
    TemporalGrouping,
    TemporalPeriod,
)
from orchestrator.search.core.types import ActionType, EntityType
from orchestrator.search.filters import FilterTree
from orchestrator.search.query.builder import build_aggregation_query, build_candidate_query
from orchestrator.search.query.mixins import OrderBy, OrderDirection
from orchestrator.search.query.queries import AggregateQuery, CountQuery, ExportQuery, Query, SelectQuery

pytestmark = pytest.mark.search


class TestSelectQueryConstruction:
    """Test SelectQuery construction with various combinations."""

    def test_minimal_select_query(self, select_query_minimal: SelectQuery):
        """Test creating a minimal SelectQuery with only required fields."""
        assert select_query_minimal.action == ActionType.SELECT
        assert select_query_minimal.limit == 10  # default
        assert select_query_minimal.query_text is None
        assert select_query_minimal.filters is None

    def test_select_query_with_text_search(self):
        """Test SelectQuery with single word text search."""
        query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text="test")

        assert query.vector_query is not None
        assert query.fuzzy_term is not None  # single word gets fuzzy

    def test_select_query_with_multi_word_text(self):
        """Test SelectQuery with multi-word text (no fuzzy search)."""
        query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text="multiple word search")

        assert query.vector_query is not None
        assert query.fuzzy_term is None  # only single words get fuzzy

    def test_select_query_with_uuid_text(self):
        """Test SelectQuery with UUID (no vector search)."""
        uuid_str = "12345678-1234-1234-1234-123456789abc"
        query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=uuid_str)

        assert query.vector_query is None  # UUIDs don't get vectorized
        assert query.fuzzy_term is not None  # but can use fuzzy

    def test_select_query_with_filters(self, select_query_with_filters: SelectQuery):
        """Test SelectQuery with structured filters."""
        assert select_query_with_filters.filters is not None


class TestExportQueryConstruction:
    """Test ExportQuery construction with higher limits."""

    def test_export_query_limits(self, export_query_minimal: ExportQuery):
        """Test ExportQuery has higher limits than SelectQuery for bulk exports."""
        # Default export limit (1000 vs SelectQuery's 10)
        assert export_query_minimal.limit == 1000

        # Max export limit (10000 vs SelectQuery's 30)
        query_max = ExportQuery(entity_type=EntityType.SUBSCRIPTION, limit=10000)
        assert query_max.limit == 10000


class TestCountQueryConstruction:
    """Test CountQuery construction with grouping options."""

    def test_minimal_count_query(self, count_query_simple: CountQuery):
        """Test creating a minimal CountQuery (simple count)."""
        assert count_query_simple.action == ActionType.COUNT
        assert count_query_simple.group_by is None
        assert count_query_simple.temporal_group_by is None

    def test_count_query_with_multiple_group_by(self, count_query_grouped: CountQuery):
        """Test CountQuery with multiple group_by fields."""
        assert count_query_grouped.group_by is not None
        assert count_query_grouped.get_pivot_fields() == ["subscription.status", "subscription.product.name"]

    def test_count_query_with_temporal_grouping(self, count_query_temporal: CountQuery):
        """Test CountQuery with temporal grouping."""
        assert count_query_temporal.temporal_group_by is not None

    def test_count_query_with_both_groupings(self, temporal_grouping_year: TemporalGrouping):
        """Test CountQuery with both regular and temporal grouping."""
        query = CountQuery(
            entity_type=EntityType.SUBSCRIPTION,
            group_by=["subscription.status"],
            temporal_group_by=[temporal_grouping_year],
        )

        pivot_fields = query.get_pivot_fields()
        assert "subscription.status" in pivot_fields
        assert "subscription.start_date" in pivot_fields

    def test_count_query_pivot_fields_deduplication(self, temporal_grouping_month: TemporalGrouping):
        """Test that get_pivot_fields deduplicates fields."""
        query = CountQuery(
            entity_type=EntityType.SUBSCRIPTION,
            group_by=["subscription.status", "subscription.start_date"],
            temporal_group_by=[temporal_grouping_month],
        )

        pivot_fields = query.get_pivot_fields()
        # Should deduplicate subscription.start_date
        assert pivot_fields.count("subscription.start_date") == 1

    def test_count_query_with_filters(self, simple_filter_tree: FilterTree):
        """Test CountQuery with filters."""
        query = CountQuery(
            entity_type=EntityType.SUBSCRIPTION,
            filters=simple_filter_tree,
            group_by=["subscription.product.name"],
        )

        assert query.filters is not None
        assert query.group_by is not None


class TestAggregateQueryConstruction:
    """Test AggregateQuery construction with aggregations and grouping."""

    def test_minimal_aggregate_query(self):
        """Test creating an AggregateQuery with minimal aggregations."""
        agg = CountAggregation(type=AggregationType.COUNT, alias="total")
        query = AggregateQuery(entity_type=EntityType.SUBSCRIPTION, aggregations=[agg])

        assert query.action == ActionType.AGGREGATE
        assert query.aggregations is not None

    def test_aggregate_query_with_grouping(self, aggregate_query_with_grouping: AggregateQuery):
        """Test AggregateQuery with grouping."""
        assert aggregate_query_with_grouping.group_by is not None
        pivot_fields = aggregate_query_with_grouping.get_pivot_fields()
        assert "subscription.status" in pivot_fields

    def test_aggregate_query_pivot_fields_includes_aggregation_fields(self, sum_aggregation: FieldAggregation):
        """Test that get_pivot_fields includes both grouping and aggregation fields."""
        query = AggregateQuery(
            entity_type=EntityType.SUBSCRIPTION,
            aggregations=[sum_aggregation],
            group_by=["subscription.status"],
        )

        pivot_fields = query.get_pivot_fields()
        assert "subscription.status" in pivot_fields
        assert "subscription.price" in pivot_fields

    def test_aggregate_query_with_temporal_grouping(
        self, count_aggregation: CountAggregation, temporal_grouping_month: TemporalGrouping
    ):
        """Test AggregateQuery with temporal grouping."""
        query = AggregateQuery(
            entity_type=EntityType.SUBSCRIPTION,
            aggregations=[count_aggregation],
            temporal_group_by=[temporal_grouping_month],
        )

        assert query.temporal_group_by is not None
        pivot_fields = query.get_pivot_fields()
        assert "subscription.start_date" in pivot_fields

    def test_aggregate_query_complex_combination(
        self,
        count_aggregation: CountAggregation,
        sum_aggregation: FieldAggregation,
        avg_aggregation: FieldAggregation,
        simple_filter_tree: FilterTree,
    ):
        """Test AggregateQuery with complex combination of features."""
        temporal = TemporalGrouping(field="subscription.start_date", period=TemporalPeriod.QUARTER)

        query = AggregateQuery(
            entity_type=EntityType.SUBSCRIPTION,
            aggregations=[count_aggregation, sum_aggregation, avg_aggregation],
            group_by=["subscription.status", "subscription.product.name"],
            temporal_group_by=[temporal],
            filters=simple_filter_tree,
        )

        assert query.aggregations is not None
        assert query.group_by is not None
        assert query.filters is not None
        pivot_fields = query.get_pivot_fields()
        # Should include group_by fields, temporal fields, and aggregation fields
        assert "subscription.status" in pivot_fields
        assert "subscription.product.name" in pivot_fields
        assert "subscription.start_date" in pivot_fields
        assert "subscription.price" in pivot_fields

    def test_aggregate_query_multiple_temporal_groupings(
        self, count_aggregation: CountAggregation, temporal_grouping_year: TemporalGrouping
    ):
        """Test AggregateQuery with multiple temporal groupings."""
        temporal2 = TemporalGrouping(field="subscription.end_date", period=TemporalPeriod.MONTH)

        query = AggregateQuery(
            entity_type=EntityType.SUBSCRIPTION,
            aggregations=[count_aggregation],
            temporal_group_by=[temporal_grouping_year, temporal2],
        )

        pivot_fields = query.get_pivot_fields()
        assert "subscription.start_date" in pivot_fields
        assert "subscription.end_date" in pivot_fields


class TestAggregationBuilderFeatures:
    """Test helper behaviors in aggregation builder."""

    @pytest.mark.parametrize(
        "query_factory,error_match",
        [
            (
                lambda: CountQuery(entity_type=EntityType.SUBSCRIPTION, cumulative=True),
                "cumulative requires at least one temporal grouping",
            ),
            (
                lambda: CountQuery(
                    entity_type=EntityType.SUBSCRIPTION,
                    order_by=[OrderBy(field="count", direction=OrderDirection.DESC)],
                ),
                "order_by requires at least one grouping field",
            ),
            (
                lambda: AggregateQuery(
                    entity_type=EntityType.SUBSCRIPTION,
                    aggregations=[],
                    group_by=["subscription.status"],
                ),
                "at least 1 item",
            ),
        ],
        ids=["cumulative-needs-temporal", "order_by-needs-grouping", "aggregations-required"],
    )
    def test_query_validation_errors(self, query_factory, error_match):
        """Test that query construction raises appropriate validation errors."""
        with pytest.raises(ValidationError, match=error_match):
            query_factory()

    def test_order_by_uses_group_field(self):
        """Order by resolves field paths."""
        query = CountQuery(
            entity_type=EntityType.SUBSCRIPTION,
            group_by=["subscription.product.name"],
            order_by=[OrderBy(field="subscription.product.name", direction=OrderDirection.DESC)],
        )
        base_query = build_candidate_query(query)
        stmt, _ = build_aggregation_query(query, base_query)
        sql = str(stmt.compile())

        assert "ORDER BY" in sql.upper()
        assert "DESC" in sql.upper()

    @pytest.mark.parametrize(
        "agg_type",
        [AggregationType.AVG, AggregationType.MIN, AggregationType.MAX],
        ids=["avg", "min", "max"],
    )
    def test_cumulative_rejects_unsupported_aggregations(
        self,
        temporal_grouping_month: TemporalGrouping,
        agg_type: AggregationType,
    ):
        """Cumulative with AVG/MIN/MAX aggregations raises validation error at query construction.

        These aggregation types are rejected because running versions (e.g., running average,
        running minimum) have no clear business meaning for cumulative totals.
        """
        with pytest.raises(ValidationError, match=f"not supported for {agg_type.value.upper()} aggregations"):
            AggregateQuery(
                entity_type=EntityType.SUBSCRIPTION,
                aggregations=[
                    FieldAggregation(type=agg_type, field="subscription.price", alias="test_agg"),  # type: ignore[list-item]
                ],
                temporal_group_by=[temporal_grouping_month],
                cumulative=True,
            )

    def test_cumulative_allows_sum_aggregation(self, temporal_grouping_month: TemporalGrouping):
        """Cumulative with SUM aggregation generates correct SQL."""
        query = AggregateQuery(
            entity_type=EntityType.SUBSCRIPTION,
            aggregations=[
                FieldAggregation(type=AggregationType.SUM, field="subscription.price", alias="total_revenue"),  # type: ignore[list-item]
            ],
            temporal_group_by=[temporal_grouping_month],
            cumulative=True,
        )
        base_query = build_candidate_query(query)
        stmt, _ = build_aggregation_query(query, base_query)

        sql = str(stmt.compile()).lower()
        assert "over" in sql  # Window function for cumulative
        assert "total_revenue_cumulative" in sql  # Cumulative column alias

    def test_cumulative_multiple_temporal_rejected(self, temporal_grouping_month: TemporalGrouping):
        """Cumulative with multiple temporal groupings raises validation error at construction time."""
        temporal_grouping_end_date = TemporalGrouping(
            field="subscription.end_date",
            period=TemporalPeriod.MONTH,
        )

        with pytest.raises(ValidationError, match="supports only a single temporal grouping"):
            CountQuery(
                entity_type=EntityType.SUBSCRIPTION,
                temporal_group_by=[temporal_grouping_month, temporal_grouping_end_date],
                cumulative=True,
            )


class TestQueryDiscriminator:
    """Test Pydantic discriminated union for Query type."""

    def test_discriminator_routes_to_select(self):
        """Test discriminator correctly creates SelectQuery."""
        data = {"query_type": "select", "entity_type": "SUBSCRIPTION"}
        from pydantic import TypeAdapter

        adapter = TypeAdapter(Query)
        query = adapter.validate_python(data)

        assert isinstance(query, SelectQuery)

    def test_discriminator_invalid_query_type(self):
        """Test that invalid query_type raises validation error."""
        data = {"query_type": "invalid", "entity_type": "subscription"}
        from pydantic import TypeAdapter

        adapter = TypeAdapter(Query)
        with pytest.raises(ValidationError) as exc:
            adapter.validate_python(data)
        assert "query_type" in str(exc.value)
