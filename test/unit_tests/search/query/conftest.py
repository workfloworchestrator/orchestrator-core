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

from orchestrator.search.aggregations import (
    AggregationType,
    CountAggregation,
    FieldAggregation,
    TemporalGrouping,
    TemporalPeriod,
)
from orchestrator.search.core.types import BooleanOperator, EntityType, FilterOp, UIType
from orchestrator.search.filters import EqualityFilter, FilterTree, PathFilter, StringFilter
from orchestrator.search.query.queries import AggregateQuery, CountQuery, ExportQuery, SelectQuery


# =============================================================================
# Building Block Fixtures
# =============================================================================


@pytest.fixture
def simple_filter_tree() -> FilterTree:
    """Simple filter tree with status=active."""
    return FilterTree(
        op=BooleanOperator.AND,
        children=[
            PathFilter(
                path="subscription.status",
                condition=EqualityFilter(op=FilterOp.EQ, value="active"),
                value_kind=UIType.STRING,
            )
        ],
    )


@pytest.fixture
def temporal_grouping_month() -> TemporalGrouping:
    """Temporal grouping by month on start_date."""
    return TemporalGrouping(field="subscription.start_date", period=TemporalPeriod.MONTH)


@pytest.fixture
def temporal_grouping_year() -> TemporalGrouping:
    """Temporal grouping by year on start_date."""
    return TemporalGrouping(field="subscription.start_date", period=TemporalPeriod.YEAR)


@pytest.fixture
def count_aggregation() -> CountAggregation:
    """Count aggregation with alias 'count'."""
    return CountAggregation(type=AggregationType.COUNT, alias="count")


@pytest.fixture
def sum_aggregation() -> FieldAggregation:
    """Sum aggregation on subscription.price."""
    return FieldAggregation(type=AggregationType.SUM, field="subscription.price", alias="total")


@pytest.fixture
def avg_aggregation() -> FieldAggregation:
    """Average aggregation on subscription.price."""
    return FieldAggregation(type=AggregationType.AVG, field="subscription.price", alias="average")


# =============================================================================
# Query Fixtures
# =============================================================================


@pytest.fixture
def select_query_minimal() -> SelectQuery:
    """Minimal SelectQuery with no filters or search text."""
    return SelectQuery(entity_type=EntityType.SUBSCRIPTION)


@pytest.fixture
def select_query_with_text() -> SelectQuery:
    """SelectQuery with text search."""
    return SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text="fiber connection")


@pytest.fixture
def select_query_with_filters(simple_filter_tree: FilterTree) -> SelectQuery:
    """SelectQuery with structured filters."""
    return SelectQuery(entity_type=EntityType.SUBSCRIPTION, filters=simple_filter_tree)


@pytest.fixture
def select_query_full(simple_filter_tree: FilterTree) -> SelectQuery:
    """Fully-specified SelectQuery with text search, filters, and custom limit."""
    return SelectQuery(
        entity_type=EntityType.SUBSCRIPTION,
        query_text="network service",
        filters=simple_filter_tree,
        limit=20,
    )


@pytest.fixture
def export_query_minimal() -> ExportQuery:
    """Minimal ExportQuery with default limit."""
    return ExportQuery(entity_type=EntityType.SUBSCRIPTION)


@pytest.fixture
def export_query_with_filters(simple_filter_tree: FilterTree) -> ExportQuery:
    """ExportQuery with filters for bulk export."""
    return ExportQuery(
        entity_type=EntityType.SUBSCRIPTION,
        filters=simple_filter_tree,
        limit=5000,
    )


@pytest.fixture
def count_query_simple() -> CountQuery:
    """Simple CountQuery without grouping."""
    return CountQuery(entity_type=EntityType.SUBSCRIPTION)


@pytest.fixture
def count_query_grouped() -> CountQuery:
    """CountQuery with group_by fields."""
    return CountQuery(
        entity_type=EntityType.SUBSCRIPTION,
        group_by=["subscription.status", "subscription.product.name"],
    )


@pytest.fixture
def count_query_temporal(temporal_grouping_month: TemporalGrouping) -> CountQuery:
    """CountQuery with temporal grouping."""
    return CountQuery(
        entity_type=EntityType.SUBSCRIPTION,
        temporal_group_by=[temporal_grouping_month],
    )


@pytest.fixture
def count_query_full(simple_filter_tree: FilterTree, temporal_grouping_year: TemporalGrouping) -> CountQuery:
    """CountQuery with grouping, temporal grouping, and filters."""
    return CountQuery(
        entity_type=EntityType.SUBSCRIPTION,
        group_by=["subscription.status"],
        temporal_group_by=[temporal_grouping_year],
        filters=simple_filter_tree,
    )


@pytest.fixture
def aggregate_query_simple(count_aggregation: CountAggregation) -> AggregateQuery:
    """Simple AggregateQuery with count aggregation."""
    return AggregateQuery(
        entity_type=EntityType.SUBSCRIPTION,
        aggregations=[count_aggregation],
    )


@pytest.fixture
def aggregate_query_with_grouping(count_aggregation: CountAggregation) -> AggregateQuery:
    """AggregateQuery with aggregations and grouping."""
    return AggregateQuery(
        entity_type=EntityType.SUBSCRIPTION,
        aggregations=[count_aggregation],
        group_by=["subscription.status"],
    )


@pytest.fixture
def aggregate_query_full(
    count_aggregation: CountAggregation,
    sum_aggregation: FieldAggregation,
    temporal_grouping_month: TemporalGrouping,
    simple_filter_tree: FilterTree,
) -> AggregateQuery:
    """AggregateQuery with multiple aggregations, grouping, and filters."""
    return AggregateQuery(
        entity_type=EntityType.SUBSCRIPTION,
        aggregations=[count_aggregation, sum_aggregation],
        group_by=["subscription.status", "subscription.product.name"],
        temporal_group_by=[temporal_grouping_month],
        filters=simple_filter_tree,
    )
