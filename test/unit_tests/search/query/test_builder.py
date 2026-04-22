"""Tests for orchestrator.core.search.query.builder -- SQL query construction, path row processing, and ordering."""

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

from collections import namedtuple
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Row

from orchestrator.core.search.core.types import EntityType, FieldType, UIType
from orchestrator.core.search.query.builder import (
    ComponentInfo,
    LeafInfo,
    _apply_ordering,
    build_paths_query,
    process_path_rows,
)
from orchestrator.core.search.query.mixins import OrderBy, OrderDirection
from orchestrator.core.search.query.queries import CountQuery

pytestmark = pytest.mark.search

# Namedtuple that behaves like an SQLAlchemy Row for (path, value_type) access
PathRow = namedtuple("PathRow", ["path", "value_type"])


def _row(path: str, field_type: FieldType = FieldType.STRING) -> Row[Any]:
    return PathRow(path=path, value_type=field_type.value)  # type: ignore[return-value]


def _make_stmt_with_columns(column_names: list[str]) -> MagicMock:
    """Build a mock stmt whose selected_columns has .key attributes."""
    cols = []
    for name in column_names:
        col = MagicMock()
        col.key = name
        col.asc.return_value = MagicMock()
        col.desc.return_value = MagicMock()
        cols.append(col)

    stmt = MagicMock()
    stmt.selected_columns = cols
    stmt.order_by.return_value = stmt
    return stmt


# ---------------------------------------------------------------------------
# Tests: build_paths_query
# ---------------------------------------------------------------------------


def test_build_paths_query_without_prefix_no_ltree_filter():
    """No prefix -> no lquery filter in compiled SQL."""
    stmt = build_paths_query(EntityType.SUBSCRIPTION)
    sql = str(stmt.compile())
    assert "lquery" not in sql.lower()
    assert "~" not in sql
    assert "entity_type" in sql.lower()


def test_build_paths_query_with_prefix_includes_ltree_filter():
    """With prefix -> lquery MATCHES_LQUERY (~) operator appears in compiled SQL."""
    stmt = build_paths_query(EntityType.SUBSCRIPTION, prefix="subscription")
    sql = str(stmt.compile())
    assert "~" in sql


def test_build_paths_query_with_search_term_includes_similarity_ordering():
    """With q -> similarity ordering applied."""
    stmt = build_paths_query(EntityType.SUBSCRIPTION, q="name")
    sql = str(stmt.compile())
    assert "similarity" in sql.lower()
    assert "desc" in sql.lower()


def test_build_paths_query_without_search_term_orders_by_path():
    """Without q -> ORDER BY path (no similarity)."""
    stmt = build_paths_query(EntityType.SUBSCRIPTION)
    sql = str(stmt.compile())
    assert "similarity" not in sql.lower()
    assert "order by" in sql.lower()


def test_build_paths_query_with_prefix_and_q_combines_both():
    """With both prefix and q -> both ltree filter and similarity ordering."""
    stmt = build_paths_query(EntityType.SUBSCRIPTION, prefix="subscription", q="name")
    sql = str(stmt.compile())
    assert "similarity" in sql.lower()


@pytest.mark.parametrize(
    "entity_type",
    [
        pytest.param(EntityType.SUBSCRIPTION, id="subscription"),
        pytest.param(EntityType.PRODUCT, id="product"),
        pytest.param(EntityType.WORKFLOW, id="workflow"),
        pytest.param(EntityType.PROCESS, id="process"),
    ],
)
def test_build_paths_query_entity_type_filter_applied(entity_type: EntityType):
    """entity_type is always applied as a WHERE filter."""
    stmt = build_paths_query(entity_type)
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert entity_type.value in sql


def test_build_paths_query_group_by_path_and_value_type():
    """Query always groups by path and value_type."""
    stmt = build_paths_query(EntityType.SUBSCRIPTION)
    sql = str(stmt.compile())
    assert "group by" in sql.lower()


# ---------------------------------------------------------------------------
# Tests: process_path_rows
# ---------------------------------------------------------------------------


def test_process_path_rows_empty_rows_returns_empty_lists():
    """No rows -> empty leaves and components."""
    leaves, components = process_path_rows([])
    assert leaves == []
    assert components == []


def test_process_path_rows_simple_leaf_extracted():
    """Single segment path -> one leaf, no components."""
    rows = [_row("status")]
    leaves, components = process_path_rows(rows)
    assert len(leaves) == 1
    assert leaves[0].name == "status"
    assert UIType.STRING in [UIType(u) for u in leaves[0].ui_types]
    assert components == []


def test_process_path_rows_two_segment_path_leaf_only():
    """Two-segment path -> leaf is last segment, no intermediate components."""
    rows = [_row("subscription.status")]
    leaves, components = process_path_rows(rows)
    assert any(leaf.name == "status" for leaf in leaves)
    assert components == []


def test_process_path_rows_three_segment_path_extracts_component():
    """Three-segment path -> leaf is last, middle is a component."""
    rows = [_row("subscription.product.name")]
    leaves, components = process_path_rows(rows)
    assert any(leaf.name == "name" for leaf in leaves)
    assert any(comp.name == "product" for comp in components)
    assert all(comp.ui_types == [UIType.COMPONENT] for comp in components)


def test_process_path_rows_numeric_segments_removed():
    """Numeric segments are stripped before processing."""
    rows = [_row("subscription.0.name")]
    leaves, components = process_path_rows(rows)
    assert any(leaf.name == "name" for leaf in leaves)
    assert components == []


def test_process_path_rows_multiple_rows_same_leaf_different_types():
    """Same leaf name with different field types -> multiple ui_types."""
    rows = [
        _row("subscription.price", FieldType.INTEGER),
        _row("product.price", FieldType.FLOAT),
    ]
    leaves, _ = process_path_rows(rows)
    price_leaf = next((leaf for leaf in leaves if leaf.name == "price"), None)
    assert price_leaf is not None
    ui_type_values = [UIType(u) for u in price_leaf.ui_types]
    assert UIType.NUMBER in ui_type_values


@pytest.mark.parametrize(
    "field_type,expected_ui_type",
    [
        pytest.param(FieldType.STRING, UIType.STRING, id="string"),
        pytest.param(FieldType.INTEGER, UIType.NUMBER, id="integer"),
        pytest.param(FieldType.FLOAT, UIType.NUMBER, id="float"),
        pytest.param(FieldType.BOOLEAN, UIType.BOOLEAN, id="boolean"),
        pytest.param(FieldType.DATETIME, UIType.DATETIME, id="datetime"),
        pytest.param(FieldType.UUID, UIType.STRING, id="uuid"),
    ],
)
def test_process_path_rows_field_type_to_ui_type_mapping(field_type: FieldType, expected_ui_type: UIType):
    """FieldType is correctly mapped to UIType in leaves."""
    rows = [_row(f"subscription.field_{field_type.value}", field_type)]
    leaves, _ = process_path_rows(rows)
    assert len(leaves) == 1
    assert UIType(leaves[0].ui_types[0]) == expected_ui_type


def test_process_path_rows_leaf_paths_preserved():
    """Original path string is preserved in LeafInfo.paths."""
    path = "subscription.product.name"
    rows = [_row(path)]
    leaves, _ = process_path_rows(rows)
    leaf = next(item for item in leaves if item.name == "name")
    assert path in leaf.paths


def test_process_path_rows_components_sorted():
    """Components are sorted alphabetically."""
    rows = [
        _row("entity.zebra.field"),
        _row("entity.alpha.field"),
        _row("entity.middle.field"),
    ]
    _, components = process_path_rows(rows)
    names = [c.name for c in components]
    assert names == sorted(names)


def test_process_path_rows_returns_leaf_info_instances():
    """Returned leaves are LeafInfo instances."""
    rows = [_row("subscription.status")]
    leaves, _ = process_path_rows(rows)
    assert all(isinstance(item, LeafInfo) for item in leaves)


def test_process_path_rows_returns_component_info_instances():
    """Returned components are ComponentInfo instances."""
    rows = [_row("subscription.product.name")]
    _, components = process_path_rows(rows)
    assert all(isinstance(c, ComponentInfo) for c in components)


# ---------------------------------------------------------------------------
# Tests: _apply_ordering
# ---------------------------------------------------------------------------


def test_apply_ordering_missing_field_raises_value_error():
    """order_by referencing a non-existent column -> ValueError."""
    query = CountQuery(
        entity_type=EntityType.SUBSCRIPTION,
        group_by=["subscription.status"],
        order_by=[OrderBy(field="subscription.status", direction=OrderDirection.DESC)],
    )
    stmt = _make_stmt_with_columns(["other_column"])

    with pytest.raises(ValueError, match="Cannot order by"):
        _apply_ordering(stmt, query, ["other_column"])


def test_apply_ordering_exact_match():
    """order_by with exact column key match -> order_by called on stmt."""
    query = CountQuery(
        entity_type=EntityType.SUBSCRIPTION,
        group_by=["subscription.status"],
        order_by=[OrderBy(field="subscription_status", direction=OrderDirection.ASC)],
    )
    stmt = _make_stmt_with_columns(["subscription_status", "count"])

    _apply_ordering(stmt, query, ["subscription_status"])
    stmt.order_by.assert_called_once()


def test_apply_ordering_normalized_field_path():
    """order_by with dot-notation field resolved via field_to_alias."""
    query = CountQuery(
        entity_type=EntityType.SUBSCRIPTION,
        group_by=["subscription.status"],
        order_by=[OrderBy(field="subscription.status", direction=OrderDirection.DESC)],
    )
    stmt = _make_stmt_with_columns(["subscription_status", "count"])

    _apply_ordering(stmt, query, ["subscription_status"])
    stmt.order_by.assert_called_once()


def test_apply_ordering_no_order_by_no_temporal_returns_stmt_unchanged():
    """No order_by and no temporal_group_by -> stmt returned unchanged."""
    query = CountQuery(entity_type=EntityType.SUBSCRIPTION)
    stmt = _make_stmt_with_columns(["count"])

    result = _apply_ordering(stmt, query, [])
    stmt.order_by.assert_not_called()
    assert result is stmt


def test_apply_ordering_temporal_group_by_default_ordering():
    """With temporal_group_by but no order_by -> default ascending ordering applied."""
    from orchestrator.core.search.aggregations import TemporalGrouping, TemporalPeriod

    temporal = TemporalGrouping(field="subscription.start_date", period=TemporalPeriod.MONTH)
    query = CountQuery(
        entity_type=EntityType.SUBSCRIPTION,
        temporal_group_by=[temporal],
    )
    alias = temporal.alias
    stmt = _make_stmt_with_columns([alias, "count"])

    _apply_ordering(stmt, query, [alias])
    stmt.order_by.assert_called_once()


def test_apply_ordering_temporal_alias_lookup():
    """order_by using temporal alias is resolved correctly."""
    from orchestrator.core.search.aggregations import TemporalGrouping, TemporalPeriod

    temporal = TemporalGrouping(field="subscription.start_date", period=TemporalPeriod.MONTH)
    alias = temporal.alias
    query = CountQuery(
        entity_type=EntityType.SUBSCRIPTION,
        temporal_group_by=[temporal],
        order_by=[OrderBy(field=alias, direction=OrderDirection.ASC)],
    )
    stmt = _make_stmt_with_columns([alias, "count"])

    _apply_ordering(stmt, query, [alias])
    stmt.order_by.assert_called_once()
