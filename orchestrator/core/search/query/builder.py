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

from collections import defaultdict
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Select, String, bindparam, case, cast, func, or_, select
from sqlalchemy.engine import Row
from sqlalchemy.sql.elements import Label
from sqlalchemy.sql.selectable import CTE
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.db.models import AiSearchIndex, AiSearchPaths
from orchestrator.core.search.aggregations import AggregationType, BaseAggregation, CountAggregation
from orchestrator.core.search.core.types import (
    EntityType,
    FieldType,
    FilterOp,
    ResponseColumnData,
    ResponseColumnValue,
    UIType,
)
from orchestrator.core.search.filters import LtreeFilter
from orchestrator.core.search.filters.ltree_filters import _LQuery
from orchestrator.core.search.indexing.field_types import is_list_path
from orchestrator.core.search.query.mixins import OrderDirection
from orchestrator.core.search.query.queries import AggregateQuery, CountQuery, Query

LIST_COLUMN_WILDCARD_MARKER = ".*."


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
    """Build the query for retrieving paths and their value types for leaves/components processing.

    Reads the ai_search_paths distinct-paths table (one row per (entity_type, path, value_type)),
    so no GROUP BY is required.
    """
    stmt = select(AiSearchPaths.path, AiSearchPaths.value_type).where(AiSearchPaths.entity_type == entity_type.value)

    if prefix:
        lquery_pattern = create_path_autocomplete_lquery(prefix)
        ltree_filter = LtreeFilter(op=FilterOp.MATCHES_LQUERY, value=lquery_pattern)
        stmt = stmt.where(ltree_filter.to_expression(AiSearchPaths.path, path=""))

    if q:
        score = func.similarity(cast(AiSearchPaths.path, String), q)
        stmt = stmt.order_by(score.desc(), AiSearchPaths.path)
    else:
        stmt = stmt.order_by(AiSearchPaths.path)

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


def _build_pivot_columns(field_paths: list[str]) -> list:
    """Build MAX(CASE ...) pivot column expressions for the given field paths."""
    return [
        func.max(case((AiSearchIndex.path == Ltree(field_path), AiSearchIndex.value), else_=None)).label(
            BaseAggregation.field_to_alias(field_path)
        )
        for field_path in field_paths
    ]


def _build_pivot_cte(base_query: Select, pivot_fields: list[str]) -> CTE:
    """Build CTE that pivots EAV rows into columns using CASE WHEN."""
    pivot_columns = [AiSearchIndex.entity_id.label("entity_id")] + _build_pivot_columns(pivot_fields)

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
    query: CountQuery | AggregateQuery,
    pivot_cte: CTE,
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


def _apply_cumulative_aggregations(
    stmt: Select,
    query: CountQuery | AggregateQuery,
    group_column_names: list[str],
    aggregation_columns: list[Label],
) -> Select:
    """Add cumulative aggregation columns."""

    # At this point, cumulative validation has already happened at query build time
    # in GroupingMixin.validate_grouping_constraints, so we know:
    # temporal_group_by exists and has exactly 1 element when cumulative=True
    if not query.cumulative or not aggregation_columns or not query.temporal_group_by:
        return stmt

    temporal_alias = query.temporal_group_by[0].alias

    base_subquery = stmt.subquery()
    partition_cols = [base_subquery.c[name] for name in group_column_names if name != temporal_alias]
    order_col = base_subquery.c[temporal_alias]

    base_columns = [base_subquery.c[col] for col in base_subquery.c.keys()]

    cumulative_columns = []
    for agg_col in aggregation_columns:
        cumulative_alias = f"{agg_col.key}_cumulative"
        over_kwargs: dict[str, Any] = {"order_by": order_col}
        if partition_cols:
            over_kwargs["partition_by"] = partition_cols
        cumulative_expr = func.sum(base_subquery.c[agg_col.key]).over(**over_kwargs).label(cumulative_alias)
        cumulative_columns.append(cumulative_expr)

    return select(*(base_columns + cumulative_columns)).select_from(base_subquery)


def _apply_ordering(
    stmt: Select,
    query: CountQuery | AggregateQuery,
    group_column_names: list[str],
) -> Select:
    """Apply ordering instructions to the SELECT statement."""
    columns_by_key = {col.key: col for col in stmt.selected_columns}

    if query.order_by:
        order_expressions = []
        for instruction in query.order_by:
            # 1) exact match
            col = columns_by_key.get(instruction.field)
            if col is None:
                # 2) temporal alias,
                for tg in query.temporal_group_by or []:
                    if instruction.field == tg.field or instruction.field == tg.alias:
                        col = columns_by_key.get(tg.alias)
                        if col is not None:
                            break
                if col is None:
                    # 3) normalized field path
                    col = columns_by_key.get(BaseAggregation.field_to_alias(instruction.field))
            if col is None:
                raise ValueError(f"Cannot order by '{instruction.field}'; column not found.")
            order_expressions.append(col.desc() if instruction.direction == OrderDirection.DESC else col.asc())
        return stmt.order_by(*order_expressions)

    if query.temporal_group_by:
        # Default ordering by all grouping columns (ascending)
        order_expressions = [columns_by_key[col_name].asc() for col_name in group_column_names]
        return stmt.order_by(*order_expressions)

    return stmt


def build_response_columns_query(
    entity_ids: list[str],
    entity_type: EntityType,
    response_columns: list[str],
) -> Select:
    """Build a pivot query that returns requested field paths as columns for the given entities.

    Uses the same MAX(CASE ...) pivot pattern as _build_pivot_cte().

    Args:
        entity_ids: List of entity IDs to fetch columns for.
        entity_type: The entity type being searched.
        response_columns: Field paths to pivot into columns.

    Returns:
        Select statement with entity_id + one column per requested path.
    """
    pivot_columns = (
        [AiSearchIndex.entity_id.label("entity_id")]
        + _build_pivot_columns(response_columns)
        + _build_pivot_type_columns(response_columns)
    )

    return (
        select(*pivot_columns)
        .where(
            AiSearchIndex.entity_id.in_(entity_ids),
            AiSearchIndex.entity_type == entity_type.value,
            AiSearchIndex.path.in_([Ltree(p) for p in response_columns]),
        )
        .group_by(AiSearchIndex.entity_id)
    )


def _type_alias(field_path: str) -> str:
    """Alias of the pivot column that carries the value_type for a field path."""
    return f"{BaseAggregation.field_to_alias(field_path)}__type"


def _build_pivot_type_columns(field_paths: list[str]) -> list:
    """Build MAX(CASE ...) pivot columns carrying the indexed value_type per field path."""
    return [
        func.max(
            case((AiSearchIndex.path == Ltree(field_path), cast(AiSearchIndex.value_type, String)), else_=None)
        ).label(_type_alias(field_path))
        for field_path in field_paths
    ]


def _restore_value_type(value: str | None, value_type: str | None) -> ResponseColumnValue:
    """Convert the TEXT stored in the index back to the Python type recorded in value_type."""
    if value is None:
        return None
    match FieldType(value_type) if value_type else FieldType.STRING:
        case FieldType.BOOLEAN:
            return value.lower() == "true"
        case FieldType.INTEGER:
            return int(value)
        case FieldType.FLOAT:
            return float(value)
        case _:
            return value


def process_response_columns(
    rows: Sequence[Row],
    response_columns: list[str],
) -> ResponseColumnData:
    """Convert pivot query rows into a mapping of entity_id -> {path: value}.

    Values are restored to the Python type recorded in the index's value_type column
    (bool, int, float); every other type is returned as the stored string.

    Args:
        rows: Result rows from build_response_columns_query.
        response_columns: The original field paths requested.

    Returns:
        Dict mapping entity_id to a dict of path -> typed value (or None).
    """

    def convert(row: Row, path: str) -> ResponseColumnValue:
        value = getattr(row, BaseAggregation.field_to_alias(path), None)
        return _restore_value_type(None if value is None else str(value), getattr(row, _type_alias(path), None))

    return {str(row.entity_id): {path: convert(row, path) for path in response_columns} for row in rows}


def _list_prefix(entity_type: EntityType, path: str) -> str | None:
    """Return the leading segment of `path` that names a list field, if any."""
    segments = path.split(".")
    prefixes = (".".join(segments[:i]) for i in range(1, len(segments)))
    return next((prefix for prefix in prefixes if is_list_path(entity_type, prefix)), None)


def _as_list_path(entity_type: EntityType, column: str) -> str | None:
    """Return `column` normalized to wildcard form if it is a list path, else None."""
    if LIST_COLUMN_WILDCARD_MARKER in column:
        return column

    list_prefix = _list_prefix(entity_type, column)
    if list_prefix is None:
        return None

    suffix = column[len(list_prefix) + 1 :]
    if suffix.partition(".")[0].isdigit():
        return None

    return f"{list_prefix}{LIST_COLUMN_WILDCARD_MARKER}{suffix}"


def split_response_columns(response_columns: list[str], entity_type: EntityType) -> tuple[list[str], list[str]]:
    """Split response columns into flat (scalar) paths and wildcard list paths.

    A plain path through a schema-known list field is auto-detected and normalized to wildcard form.
    A path pinning a concrete numeric index stays flat.
    """
    resolved = [(column, _as_list_path(entity_type, column)) for column in response_columns]
    flat_paths = [column for column, list_path in resolved if list_path is None]
    list_paths = [list_path for _, list_path in resolved if list_path is not None]
    return flat_paths, list_paths


def build_response_list_rows_query(
    entity_ids: list[str],
    entity_type: EntityType,
    list_paths: list[str],
) -> Select:
    """Build a query returning the raw EAV rows for one or more wildcard list paths in a single round-trip.

    Unlike build_response_columns_query, this does not pivot in SQL: it fetches one row per
    (entity_id, path) match and leaves grouping/merging by list index to process_response_list_columns.
    """
    prefixes = {path.partition(LIST_COLUMN_WILDCARD_MARKER)[0] for path in list_paths}
    lquery_matches = [
        AiSearchIndex.path.op("~")(bindparam(None, f"{prefix}.*.*", type_=_LQuery())) for prefix in prefixes
    ]

    return select(AiSearchIndex.entity_id, AiSearchIndex.path, AiSearchIndex.value, AiSearchIndex.value_type).where(
        AiSearchIndex.entity_id.in_(entity_ids),
        AiSearchIndex.entity_type == entity_type.value,
        or_(*lquery_matches),
    )


def _group_suffixes_by_prefix(list_paths: list[str]) -> dict[str, set[str]]:
    """Group wildcard list paths into a prefix -> requested suffixes mapping."""
    requested_suffixes: dict[str, set[str]] = defaultdict(set)
    for path in list_paths:
        prefix, _, suffix = path.partition(LIST_COLUMN_WILDCARD_MARKER)
        requested_suffixes[prefix].add(suffix)
    return requested_suffixes


def _match_list_row(path_str: str, requested_suffixes: dict[str, set[str]]) -> tuple[str, int, str] | None:
    """Return the (prefix, index, suffix) a row's path matches, or None if it matches no requested path."""
    matching_prefixes = [prefix for prefix in requested_suffixes if path_str.startswith(f"{prefix}.")]
    if not matching_prefixes:
        return None

    prefix = max(matching_prefixes, key=len)
    tail = path_str[len(prefix) + 1 :]
    index_str, _, suffix = tail.partition(".")
    if suffix not in requested_suffixes[prefix]:
        return None

    return prefix, int(index_str), suffix


def process_response_list_columns(
    rows: Sequence[Row],
    list_paths: list[str],
) -> dict[str, dict[str, list[dict[str, ResponseColumnValue]]]]:
    """Group raw EAV rows for wildcard list paths into prefix -> entity_id -> ordered items.

    Values are restored to their indexed Python type.
    Every prefix in list_paths is included in the result, even with zero matching rows.
    """
    requested_suffixes = _group_suffixes_by_prefix(list_paths)
    items_by_group: dict[str, dict[str, dict[int, dict[str, ResponseColumnValue]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )

    for row in rows:
        match = _match_list_row(str(row.path), requested_suffixes)
        if match is not None:
            prefix, index, suffix = match
            value = row.value
            items_by_group[prefix][str(row.entity_id)][index][suffix] = _restore_value_type(
                None if value is None else str(value), row.value_type
            )

    return {
        prefix: {
            entity_id: [item for _, item in sorted(items.items())]
            for entity_id, items in items_by_group.get(prefix, {}).items()
        }
        for prefix in requested_suffixes
    }


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

    stmt = _apply_cumulative_aggregations(stmt, query, group_col_names, agg_cols)
    stmt = _apply_ordering(stmt, query, group_col_names)

    return stmt, group_col_names
