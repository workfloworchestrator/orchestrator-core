"""Tests for orchestrator.search.query.queries -- query construction, validation, aggregation builders, and discriminated union routing."""

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

from unittest.mock import MagicMock

import pytest
from pydantic import TypeAdapter, ValidationError

from orchestrator.search.aggregations import (
    AggregationType,
    BaseAggregation,
    CountAggregation,
    FieldAggregation,
    TemporalGrouping,
    TemporalPeriod,
)
from orchestrator.search.core.types import EntityType, QueryOperation
from orchestrator.search.filters import FilterTree
from orchestrator.search.query.builder import build_aggregation_query, build_candidate_query
from orchestrator.search.query.mixins import OrderBy, OrderDirection
from orchestrator.search.query.queries import AggregateQuery, CountQuery, ExportQuery, Query, SelectQuery

pytestmark = pytest.mark.search


# ---------------------------------------------------------------------------
# SelectQuery construction
# ---------------------------------------------------------------------------


def test_select_query_minimal(select_query_minimal: SelectQuery):
    """Minimal SelectQuery with only required fields."""
    assert select_query_minimal.query_type == "select"
    assert select_query_minimal.limit == 10
    assert select_query_minimal.query_text is None
    assert select_query_minimal.filters is None


def test_select_query_with_text_search():
    """SelectQuery with single word text search."""
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text="test")
    assert query.vector_query is not None
    assert query.fuzzy_term is not None


def test_select_query_with_multi_word_text():
    """SelectQuery with multi-word text (no fuzzy search)."""
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text="multiple word search")
    assert query.vector_query is not None
    assert query.fuzzy_term is None


def test_select_query_with_uuid_text():
    """SelectQuery with UUID (no vector search)."""
    uuid_str = "12345678-1234-1234-1234-123456789abc"
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=uuid_str)
    assert query.vector_query is None
    assert query.fuzzy_term is not None


def test_select_query_with_filters(select_query_with_filters: SelectQuery):
    """SelectQuery with structured filters."""
    assert select_query_with_filters.filters is not None


# ---------------------------------------------------------------------------
# ExportQuery construction
# ---------------------------------------------------------------------------


def test_export_query_limits(export_query_minimal: ExportQuery):
    """ExportQuery has higher limits than SelectQuery for bulk exports."""
    assert export_query_minimal.limit == 1000
    query_max = ExportQuery(entity_type=EntityType.SUBSCRIPTION, limit=10000)
    assert query_max.limit == 10000


# ---------------------------------------------------------------------------
# CountQuery construction
# ---------------------------------------------------------------------------


def test_count_query_minimal(count_query_simple: CountQuery):
    """Minimal CountQuery (simple count)."""
    assert count_query_simple.query_type == "count"
    assert count_query_simple.group_by is None
    assert count_query_simple.temporal_group_by is None


def test_count_query_with_multiple_group_by(count_query_grouped: CountQuery):
    """CountQuery with multiple group_by fields."""
    assert count_query_grouped.group_by is not None
    assert count_query_grouped.get_pivot_fields() == ["subscription.status", "subscription.product.name"]


def test_count_query_with_temporal_grouping(count_query_temporal: CountQuery):
    """CountQuery with temporal grouping."""
    assert count_query_temporal.temporal_group_by is not None


def test_count_query_with_both_groupings(temporal_grouping_year: TemporalGrouping):
    """CountQuery with both regular and temporal grouping."""
    query = CountQuery(
        entity_type=EntityType.SUBSCRIPTION,
        group_by=["subscription.status"],
        temporal_group_by=[temporal_grouping_year],
    )
    pivot_fields = query.get_pivot_fields()
    assert "subscription.status" in pivot_fields
    assert "subscription.start_date" in pivot_fields


def test_count_query_pivot_fields_deduplication(temporal_grouping_month: TemporalGrouping):
    """get_pivot_fields deduplicates fields."""
    query = CountQuery(
        entity_type=EntityType.SUBSCRIPTION,
        group_by=["subscription.status", "subscription.start_date"],
        temporal_group_by=[temporal_grouping_month],
    )
    pivot_fields = query.get_pivot_fields()
    assert pivot_fields.count("subscription.start_date") == 1


def test_count_query_with_filters(simple_filter_tree: FilterTree):
    """CountQuery with filters."""
    query = CountQuery(
        entity_type=EntityType.SUBSCRIPTION,
        filters=simple_filter_tree,
        group_by=["subscription.product.name"],
    )
    assert query.filters is not None
    assert query.group_by is not None


# ---------------------------------------------------------------------------
# AggregateQuery construction
# ---------------------------------------------------------------------------


def test_aggregate_query_minimal():
    """AggregateQuery with minimal aggregations."""
    agg = CountAggregation(type=AggregationType.COUNT, alias="total")
    query = AggregateQuery(entity_type=EntityType.SUBSCRIPTION, aggregations=[agg])
    assert query.query_type == QueryOperation.AGGREGATE
    assert query.aggregations is not None


def test_aggregate_query_with_grouping(aggregate_query_with_grouping: AggregateQuery):
    """AggregateQuery with grouping."""
    assert aggregate_query_with_grouping.group_by is not None
    pivot_fields = aggregate_query_with_grouping.get_pivot_fields()
    assert "subscription.status" in pivot_fields


def test_aggregate_query_pivot_fields_includes_aggregation_fields(sum_aggregation: FieldAggregation):
    """get_pivot_fields includes both grouping and aggregation fields."""
    query = AggregateQuery(
        entity_type=EntityType.SUBSCRIPTION,
        aggregations=[sum_aggregation],
        group_by=["subscription.status"],
    )
    pivot_fields = query.get_pivot_fields()
    assert "subscription.status" in pivot_fields
    assert "subscription.price" in pivot_fields


def test_aggregate_query_with_temporal_grouping(
    count_aggregation: CountAggregation, temporal_grouping_month: TemporalGrouping
):
    """AggregateQuery with temporal grouping."""
    query = AggregateQuery(
        entity_type=EntityType.SUBSCRIPTION,
        aggregations=[count_aggregation],
        temporal_group_by=[temporal_grouping_month],
    )
    assert query.temporal_group_by is not None
    pivot_fields = query.get_pivot_fields()
    assert "subscription.start_date" in pivot_fields


def test_aggregate_query_complex_combination(
    count_aggregation: CountAggregation,
    sum_aggregation: FieldAggregation,
    avg_aggregation: FieldAggregation,
    simple_filter_tree: FilterTree,
):
    """AggregateQuery with complex combination of features."""
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
    assert "subscription.status" in pivot_fields
    assert "subscription.product.name" in pivot_fields
    assert "subscription.start_date" in pivot_fields
    assert "subscription.price" in pivot_fields


def test_aggregate_query_multiple_temporal_groupings(
    count_aggregation: CountAggregation, temporal_grouping_year: TemporalGrouping
):
    """AggregateQuery with multiple temporal groupings."""
    temporal2 = TemporalGrouping(field="subscription.end_date", period=TemporalPeriod.MONTH)
    query = AggregateQuery(
        entity_type=EntityType.SUBSCRIPTION,
        aggregations=[count_aggregation],
        temporal_group_by=[temporal_grouping_year, temporal2],
    )
    pivot_fields = query.get_pivot_fields()
    assert "subscription.start_date" in pivot_fields
    assert "subscription.end_date" in pivot_fields


# ---------------------------------------------------------------------------
# Query validation errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query_factory,error_match",
    [
        pytest.param(
            lambda: CountQuery(entity_type=EntityType.SUBSCRIPTION, cumulative=True),
            "cumulative requires at least one temporal grouping",
            id="cumulative-needs-temporal",
        ),
        pytest.param(
            lambda: CountQuery(
                entity_type=EntityType.SUBSCRIPTION,
                order_by=[OrderBy(field="count", direction=OrderDirection.DESC)],
            ),
            "order_by requires at least one grouping field",
            id="order_by-needs-grouping",
        ),
        pytest.param(
            lambda: AggregateQuery(
                entity_type=EntityType.SUBSCRIPTION,
                aggregations=[],
                group_by=["subscription.status"],
            ),
            "at least 1 item",
            id="aggregations-required",
        ),
    ],
)
def test_query_validation_errors(query_factory, error_match):
    """Query construction raises appropriate validation errors."""
    with pytest.raises(ValidationError, match=error_match):
        query_factory()


def test_order_by_uses_group_field():
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
    [
        pytest.param(AggregationType.AVG, id="avg"),
        pytest.param(AggregationType.MIN, id="min"),
        pytest.param(AggregationType.MAX, id="max"),
    ],
)
def test_cumulative_rejects_unsupported_aggregations(
    temporal_grouping_month: TemporalGrouping,
    agg_type: AggregationType,
):
    """Cumulative with AVG/MIN/MAX aggregations raises validation error at query construction."""
    with pytest.raises(ValidationError, match=f"not supported for {agg_type.value.upper()} aggregations"):
        AggregateQuery(
            entity_type=EntityType.SUBSCRIPTION,
            aggregations=[
                FieldAggregation(type=agg_type, field="subscription.price", alias="test_agg"),  # type: ignore[arg-type]
            ],
            temporal_group_by=[temporal_grouping_month],
            cumulative=True,
        )


def test_cumulative_allows_sum_aggregation(temporal_grouping_month: TemporalGrouping):
    """Cumulative with SUM aggregation generates correct SQL."""
    query = AggregateQuery(
        entity_type=EntityType.SUBSCRIPTION,
        aggregations=[
            FieldAggregation(type=AggregationType.SUM, field="subscription.price", alias="total_revenue"),
        ],
        temporal_group_by=[temporal_grouping_month],
        cumulative=True,
    )
    base_query = build_candidate_query(query)
    stmt, _ = build_aggregation_query(query, base_query)
    sql = str(stmt.compile()).lower()
    assert "over" in sql
    assert "total_revenue_cumulative" in sql


def test_cumulative_multiple_temporal_rejected(temporal_grouping_month: TemporalGrouping):
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


# ---------------------------------------------------------------------------
# Query discriminated union
# ---------------------------------------------------------------------------


def test_discriminator_routes_to_select():
    """Discriminator correctly creates SelectQuery."""
    data = {"query_type": "select", "entity_type": "SUBSCRIPTION"}
    adapter = TypeAdapter(Query)
    query = adapter.validate_python(data)
    assert isinstance(query, SelectQuery)


def test_discriminator_invalid_query_type():
    """Invalid query_type raises validation error."""
    data = {"query_type": "invalid", "entity_type": "subscription"}
    adapter = TypeAdapter(Query)
    with pytest.raises(ValidationError) as exc:
        adapter.validate_python(data)
    assert "query_type" in str(exc.value)


# ---------------------------------------------------------------------------
# BaseAggregation.create
# ---------------------------------------------------------------------------


def test_base_aggregation_create_count():
    """BaseAggregation.create with type=count returns CountAggregation."""
    result = BaseAggregation.create({"type": "count", "alias": "total"})
    assert isinstance(result, CountAggregation)
    assert result.alias == "total"
    assert result.type == AggregationType.COUNT


@pytest.mark.parametrize(
    "agg_type",
    [
        pytest.param(AggregationType.SUM, id="sum"),
        pytest.param(AggregationType.AVG, id="avg"),
        pytest.param(AggregationType.MIN, id="min"),
        pytest.param(AggregationType.MAX, id="max"),
    ],
)
def test_base_aggregation_create_field(agg_type: AggregationType):
    """BaseAggregation.create with field aggregation types returns FieldAggregation."""
    result = BaseAggregation.create({"type": agg_type.value, "alias": "result", "field": "subscription.price"})
    assert isinstance(result, FieldAggregation)
    assert result.type == agg_type
    assert result.field == "subscription.price"


def test_base_aggregation_create_invalid_type_raises():
    """BaseAggregation.create with unknown type raises ValidationError."""
    with pytest.raises(ValidationError):
        BaseAggregation.create({"type": "unknown", "alias": "x"})


# ---------------------------------------------------------------------------
# BaseAggregation.field_to_alias
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field_path,expected_alias",
    [
        pytest.param("subscription.name", "subscription_name", id="dot"),
        pytest.param("product.serial-number", "product_serial_number", id="dash"),
        pytest.param("subscription.product.name", "subscription_product_name", id="multi-dot"),
        pytest.param("simple", "simple", id="no-separator"),
        pytest.param("a.b-c.d", "a_b_c_d", id="mixed"),
    ],
)
def test_field_to_alias(field_path: str, expected_alias: str):
    """field_to_alias replaces dots and dashes with underscores."""
    assert BaseAggregation.field_to_alias(field_path) == expected_alias


# ---------------------------------------------------------------------------
# CountAggregation.to_expression
# ---------------------------------------------------------------------------


def test_count_aggregation_to_expression():
    """CountAggregation.to_expression returns a labeled func.count expression."""
    agg = CountAggregation(type=AggregationType.COUNT, alias="total")
    mock_col = MagicMock()
    label = agg.to_expression(mock_col)
    assert label.key == "total"


# ---------------------------------------------------------------------------
# FieldAggregation.to_expression
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "agg_type,expected_func",
    [
        pytest.param(AggregationType.SUM, "sum", id="sum"),
        pytest.param(AggregationType.AVG, "avg", id="avg"),
        pytest.param(AggregationType.MIN, "min", id="min"),
        pytest.param(AggregationType.MAX, "max", id="max"),
    ],
)
def test_field_aggregation_to_expression(agg_type: AggregationType, expected_func: str):
    """FieldAggregation.to_expression returns a labeled expression for each agg type."""
    agg = FieldAggregation(type=agg_type, field="subscription.price", alias="result")  # type: ignore[arg-type]
    pivot_cols = MagicMock()
    pivot_cols.subscription_price = MagicMock()
    label = agg.to_expression(pivot_cols)
    assert label.key == "result"


def test_field_aggregation_missing_field_raises_value_error():
    """FieldAggregation.to_expression raises ValueError when field not in pivot CTE."""
    agg = FieldAggregation(type=AggregationType.SUM, field="subscription.price", alias="result")
    pivot_cols = object()
    with pytest.raises(ValueError, match="not found in pivot CTE columns"):
        agg.to_expression(pivot_cols)


# ---------------------------------------------------------------------------
# TemporalGrouping.alias
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,period,expected_alias",
    [
        pytest.param("subscription.start_date", TemporalPeriod.MONTH, "subscription_start_date_month", id="month"),
        pytest.param("subscription.end_date", TemporalPeriod.YEAR, "subscription_end_date_year", id="year"),
        pytest.param("process.created_at", TemporalPeriod.DAY, "process_created_at_day", id="day"),
        pytest.param(
            "subscription.start_date", TemporalPeriod.QUARTER, "subscription_start_date_quarter", id="quarter"
        ),
    ],
)
def test_temporal_grouping_alias(field: str, period: TemporalPeriod, expected_alias: str):
    """TemporalGrouping.alias returns field_to_alias(field) + '_' + period.value."""
    tg = TemporalGrouping(field=field, period=period)
    assert tg.alias == expected_alias


# ---------------------------------------------------------------------------
# TemporalGrouping.to_expression
# ---------------------------------------------------------------------------


def test_temporal_grouping_to_expression_returns_3_tuple():
    """TemporalGrouping.to_expression returns (select_col, group_col, col_name) tuple."""
    tg = TemporalGrouping(field="subscription.start_date", period=TemporalPeriod.MONTH)
    pivot_cols = MagicMock()
    pivot_cols.subscription_start_date = MagicMock()
    result = tg.to_expression(pivot_cols)
    assert isinstance(result, tuple)
    assert len(result) == 3


def test_temporal_grouping_to_expression_col_name_matches_alias():
    """Third element of to_expression tuple is the alias string."""
    tg = TemporalGrouping(field="subscription.start_date", period=TemporalPeriod.MONTH)
    pivot_cols = MagicMock()
    pivot_cols.subscription_start_date = MagicMock()
    _, _, col_name = tg.to_expression(pivot_cols)
    assert col_name == tg.alias


def test_temporal_grouping_to_expression_select_col_labeled():
    """First element of to_expression tuple has the alias as its label key."""
    tg = TemporalGrouping(field="subscription.start_date", period=TemporalPeriod.MONTH)
    pivot_cols = MagicMock()
    pivot_cols.subscription_start_date = MagicMock()
    select_col, _, col_name = tg.to_expression(pivot_cols)
    assert select_col.key == col_name
