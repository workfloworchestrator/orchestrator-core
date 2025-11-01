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

from collections import defaultdict
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Select, String, case, cast, func, select
from sqlalchemy.engine import Row
from sqlalchemy.sql.elements import Label
from sqlalchemy.sql.selectable import CTE
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.db.models import AiSearchIndex
from orchestrator.search.aggregations import AggregationType, BaseAggregation, CountAggregation
from orchestrator.search.core.types import EntityType, FieldType, FilterOp, UIType
from orchestrator.search.filters import LtreeFilter
from orchestrator.search.query.queries import AggregateQuery, CountQuery, Query


class LeafInfo(BaseModel):
    """Information about a leaf (terminal field) in the entity schema."""

    name: str
    ui_types: list[UIType]
    paths: list[str]

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
    )


class ComponentInfo(BaseModel):
    """Information about a component (nested object) in the entity schema."""

    name: str
    ui_types: list[UIType]

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
    )


def create_path_autocomplete_lquery(prefix: str) -> str:
    """Create the lquery pattern for a multi-level path autocomplete search."""
    return f"{prefix}*.*"


def build_candidate_query(query: Query) -> Select:
    """Build the base query for retrieving candidate entities.

    Constructs a `SELECT` statement that retrieves distinct `entity_id` values
    from the index table for the given entity type, applying any structured
    filters from the provided query plan.

    Args:
        query: Any query type (SelectQuery, CountQuery, AggregateQuery) containing entity type and optional filters.

    Returns:
        Select: The SQLAlchemy `Select` object representing the query.
    """

    stmt = (
        select(AiSearchIndex.entity_id, AiSearchIndex.entity_title)
        .where(AiSearchIndex.entity_type == query.entity_type.value)
        .distinct()
    )

    if query.filters is not None:
        entity_id_col = AiSearchIndex.entity_id
        stmt = stmt.where(
            query.filters.to_expression(
                entity_id_col,
                entity_type_value=query.entity_type.value,
            )
        )

    return stmt


def build_paths_query(entity_type: EntityType, prefix: str | None = None, q: str | None = None) -> Select:
    """Build the query for retrieving paths and their value types for leaves/components processing."""
    stmt = select(AiSearchIndex.path, AiSearchIndex.value_type).where(AiSearchIndex.entity_type == entity_type.value)

    if prefix:
        lquery_pattern = create_path_autocomplete_lquery(prefix)
        ltree_filter = LtreeFilter(op=FilterOp.MATCHES_LQUERY, value=lquery_pattern)
        stmt = stmt.where(ltree_filter.to_expression(AiSearchIndex.path, path=""))

    stmt = stmt.group_by(AiSearchIndex.path, AiSearchIndex.value_type)

    if q:
        score = func.similarity(cast(AiSearchIndex.path, String), q)
        stmt = stmt.order_by(score.desc(), AiSearchIndex.path)
    else:
        stmt = stmt.order_by(AiSearchIndex.path)

    return stmt


def process_path_rows(rows: Sequence[Row]) -> tuple[list[LeafInfo], list[ComponentInfo]]:
    """Process query results to extract leaves and components information.

    Parameters
    ----------
    rows : Sequence[Row]
        Database rows containing path and value_type information

    Returns:
    -------
    tuple[list[LeafInfo], list[ComponentInfo]]
        Processed leaves and components
    """
    leaves_dict: dict[str, set[UIType]] = defaultdict(set)
    leaves_paths_dict: dict[str, set[str]] = defaultdict(set)
    components_set: set[str] = set()

    for row in rows:
        path, value_type = row

        path_str = str(path)
        path_segments = path_str.split(".")

        # Remove numeric segments
        clean_segments = [seg for seg in path_segments if not seg.isdigit()]

        if clean_segments:
            # Last segment is a leaf
            leaf_name = clean_segments[-1]
            ui_type = UIType.from_field_type(FieldType(value_type))
            leaves_dict[leaf_name].add(ui_type)
            leaves_paths_dict[leaf_name].add(path_str)

            # All segments except the first/last are components
            for component in clean_segments[1:-1]:
                components_set.add(component)

    leaves = [
        LeafInfo(name=leaf, ui_types=list(types), paths=sorted(leaves_paths_dict[leaf]))
        for leaf, types in leaves_dict.items()
    ]
    components = [ComponentInfo(name=component, ui_types=[UIType.COMPONENT]) for component in sorted(components_set)]

    return leaves, components


def _build_pivot_cte(base_query: Select, pivot_fields: list[str]) -> CTE:
    """Build CTE that pivots EAV rows into columns using CASE WHEN."""
    from orchestrator.search.aggregations import BaseAggregation

    pivot_columns = [AiSearchIndex.entity_id.label("entity_id")]

    for field_path in pivot_fields:
        pivot_columns.append(
            func.max(case((AiSearchIndex.path == Ltree(field_path), AiSearchIndex.value), else_=None)).label(
                BaseAggregation.field_to_alias(field_path)
            )
        )

    return (
        select(*pivot_columns)
        .where(
            AiSearchIndex.entity_id.in_(select(base_query.c.entity_id)),
            AiSearchIndex.path.in_([Ltree(p) for p in pivot_fields]),
        )
        .group_by(AiSearchIndex.entity_id)
        .cte("pivoted_entities")
    )


def _build_grouping_columns(
    query: CountQuery | AggregateQuery, pivot_cte: CTE
) -> tuple[list[Any], list[Any], list[str]]:
    """Build GROUP BY columns and their SELECT columns.

    Args:
        query: CountQuery or AggregateQuery with group_by and temporal_group_by fields
        pivot_cte: The pivoted CTE containing entity fields as columns

    Returns:
        tuple: (select_columns, group_by_columns, group_column_names)
            - select_columns: List of labeled columns for SELECT
            - group_by_columns: List of columns for GROUP BY clause
            - group_column_names: List of column names (labels) that are grouping columns
    """

    select_columns = []
    group_by_columns = []
    group_column_names = []

    if query.group_by:
        for group_field in query.group_by:
            field_alias = BaseAggregation.field_to_alias(group_field)
            col = getattr(pivot_cte.c, field_alias)
            select_columns.append(col.label(field_alias))
            group_by_columns.append(col)
            group_column_names.append(field_alias)

    if query.temporal_group_by:
        for temp_group in query.temporal_group_by:
            select_col, group_col, col_name = temp_group.to_expression(pivot_cte.c)
            select_columns.append(select_col)
            group_by_columns.append(group_col)
            group_column_names.append(col_name)

    return select_columns, group_by_columns, group_column_names


def _build_aggregation_columns(query: CountQuery | AggregateQuery, pivot_cte: CTE) -> list[Label]:
    """Build aggregation columns (COUNT, SUM, AVG, MIN, MAX).

    Args:
        query: CountQuery or AggregateQuery
        pivot_cte: The pivoted CTE containing entity fields as columns

    Returns:
        List of labeled aggregation expressions
    """

    if isinstance(query, AggregateQuery):
        # AGGREGATE query with custom aggregations
        agg_columns = []
        for agg in query.aggregations:
            if isinstance(agg, CountAggregation):
                agg_columns.append(agg.to_expression(pivot_cte.c.entity_id))
            else:
                agg_columns.append(agg.to_expression(pivot_cte.c))
        return agg_columns

    # CountQuery without aggregations
    count_agg = CountAggregation(type=AggregationType.COUNT, alias="count")
    return [count_agg.to_expression(pivot_cte.c.entity_id)]


def build_simple_count_query(base_query: Select) -> Select:
    """Build a simple count query without grouping.

    Args:
        base_query: Base candidate query with filters applied

    Returns:
        Select statement that counts distinct entity IDs
    """
    return select(func.count(func.distinct(base_query.c.entity_id)).label("total_count")).select_from(
        base_query.subquery()
    )


def build_aggregation_query(query: CountQuery | AggregateQuery, base_query: Select) -> tuple[Select, list[str]]:
    """Build aggregation query with GROUP BY and aggregation functions.

    Handles EAV storage by pivoting rows to columns, then applying SQL aggregations.
    This function only handles grouped aggregations. Simple counts are handled directly
    in the engine.

    Args:
        query: CountQuery or AggregateQuery with group_by and optional aggregations
        base_query: Base candidate query with filters applied

    Returns:
        tuple: (query_stmt, group_column_names)
            - query_stmt: SQLAlchemy Select statement for grouped aggregation
            - group_column_names: List of column names that are grouping columns
    """
    pivot_cte = _build_pivot_cte(base_query, query.get_pivot_fields())
    select_cols, group_cols, group_col_names = _build_grouping_columns(query, pivot_cte)
    agg_cols = _build_aggregation_columns(query, pivot_cte)

    stmt = select(*(select_cols + agg_cols)).select_from(pivot_cte)
    if group_cols:
        stmt = stmt.group_by(*group_cols)

    return stmt, group_col_names
