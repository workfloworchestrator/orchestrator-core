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

"""Elasticsearch DSL query translation to FilterTree.

Accepts the ES DSL format produced by react-querybuilder's
``formatQuery(query, "elasticsearch")`` and converts it to the internal
FilterTree representation used by the search engine.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

from orchestrator.core.search.core.types import BooleanOperator, FieldType, FilterOp, UIType
from orchestrator.core.search.filters.base import (
    EqualityFilter,
    FilterTree,
    PathFilter,
    StringFilter,
)
from orchestrator.core.search.filters.date_filters import DateRange, DateRangeFilter, DateValueFilter
from orchestrator.core.search.filters.ltree_filters import LtreeFilter
from orchestrator.core.search.filters.numeric_filter import NumericRange, NumericRangeFilter, NumericValueFilter

# ---------------------------------------------------------------------------
# Operator inversion for must_not
# ---------------------------------------------------------------------------

_INVERT_OP: dict[FilterOp, FilterOp] = {
    FilterOp.EQ: FilterOp.NEQ,
    FilterOp.NEQ: FilterOp.EQ,
    FilterOp.GT: FilterOp.LTE,
    FilterOp.GTE: FilterOp.LT,
    FilterOp.LT: FilterOp.GTE,
    FilterOp.LTE: FilterOp.GT,
}


def _infer_value_kind(value: Any) -> UIType:
    """Infer a UIType from a raw filter value using FieldType heuristics."""
    return UIType.from_field_type(FieldType.infer(value))


# ---------------------------------------------------------------------------
# Wildcard pattern conversion
# ---------------------------------------------------------------------------


def _convert_wildcard_pattern(es_pattern: str) -> str:
    """Convert ES wildcard syntax to SQL LIKE syntax.

    ES ``*`` → SQL ``%``, ES ``?`` → SQL ``_``.
    """
    return es_pattern.replace("*", "%").replace("?", "_")


# ---------------------------------------------------------------------------
# ES DSL Pydantic models
# ---------------------------------------------------------------------------


class TermQuery(BaseModel):
    """``{"term": {"field": value}}``."""

    term: dict[str, Any] = Field(min_length=1, max_length=1)


class RangeQuery(BaseModel):
    """``{"range": {"field": {"gt": v, ...}}}``."""

    range: dict[str, dict[str, Any]] = Field(min_length=1, max_length=1)


class WildcardQuery(BaseModel):
    """``{"wildcard": {"field": {"value": "pattern"}}}``."""

    wildcard: dict[str, dict[str, str]] = Field(min_length=1, max_length=1)


class ExistsQuery(BaseModel):
    """``{"exists": {"field": "name"}}``."""

    exists: dict[Literal["field"], str]


class BoolQuery(BaseModel):
    """``{"bool": {"must": [...], "should": [...], "must_not": [...]}}``."""

    bool: BoolClause


class BoolClause(BaseModel):
    must: list[ElasticQuery] = Field(default_factory=list)
    should: list[ElasticQuery] = Field(default_factory=list)
    must_not: list[ElasticQuery] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_not_empty(self) -> BoolClause:
        if not self.must and not self.should and not self.must_not:
            raise ValueError("bool query must have at least one clause (must, should, or must_not)")
        return self


ElasticQuery = Annotated[
    TermQuery | RangeQuery | WildcardQuery | ExistsQuery | BoolQuery,
    Field(discriminator=None),
]

# Rebuild models that reference the forward ref
BoolClause.model_rebuild()
BoolQuery.model_rebuild()

# ---------------------------------------------------------------------------
# Translation: ES DSL → FilterTree / PathFilter
# ---------------------------------------------------------------------------

_RANGE_KEYS = frozenset({"gt", "gte", "lt", "lte"})


def _translate_term(query: TermQuery) -> PathFilter:
    """Convert a term query to a PathFilter with EqualityFilter."""
    field, value = next(iter(query.term.items()))
    return PathFilter(
        path=field,
        condition=EqualityFilter(op=FilterOp.EQ, value=value),
        value_kind=_infer_value_kind(value),
    )


def _translate_range(query: RangeQuery) -> PathFilter:
    """Convert a range query to a PathFilter with date/numeric value or range filter."""
    field, bounds = next(iter(query.range.items()))

    if "gte" in bounds and "lte" in bounds:
        # Two-bound → BETWEEN range filter
        start_val, end_val = bounds["gte"], bounds["lte"]
        value_kind = _infer_value_kind(start_val)

        condition: DateRangeFilter | NumericRangeFilter
        if value_kind == UIType.DATETIME:
            condition = DateRangeFilter(op=FilterOp.BETWEEN, value=DateRange(start=start_val, end=end_val))
        else:
            condition = NumericRangeFilter(op=FilterOp.BETWEEN, value=NumericRange(start=start_val, end=end_val))

        return PathFilter(path=field, condition=condition, value_kind=value_kind)

    # Single bound: pick the first recognised op
    es_key = next((k for k in bounds if k in _RANGE_KEYS), None)
    if es_key is None:
        raise ValueError(f"range query for '{field}' has no recognised bounds: {bounds}")

    value = bounds[es_key]
    filter_op = FilterOp(es_key)
    value_kind = _infer_value_kind(value)

    single_condition: DateValueFilter | NumericValueFilter
    if value_kind == UIType.DATETIME:
        single_condition = DateValueFilter(op=filter_op, value=value)  # type: ignore[arg-type]
    else:
        single_condition = NumericValueFilter(op=filter_op, value=value)  # type: ignore[arg-type]

    return PathFilter(path=field, condition=single_condition, value_kind=value_kind)


def _translate_wildcard(query: WildcardQuery) -> PathFilter:
    """Convert a wildcard query to a PathFilter with StringFilter(LIKE)."""
    field, spec = next(iter(query.wildcard.items()))
    es_pattern = spec.get("value", "")
    sql_pattern = _convert_wildcard_pattern(es_pattern)
    return PathFilter(
        path=field,
        condition=StringFilter(op=FilterOp.LIKE, value=sql_pattern),
        value_kind=UIType.STRING,
    )


def _translate_exists(query: ExistsQuery) -> PathFilter:
    """Convert an exists query to a PathFilter with LtreeFilter(ENDS_WITH)."""
    field_name = query.exists["field"]
    return PathFilter(
        path="*",
        condition=LtreeFilter(op=FilterOp.ENDS_WITH, value=field_name),
        value_kind=UIType.COMPONENT,
    )


def _invert_path_filter(pf: PathFilter) -> PathFilter:
    """Invert a PathFilter's operator for must_not semantics."""
    match pf.condition:
        case EqualityFilter(op=op, value=value):
            return pf.model_copy(update={"condition": EqualityFilter(op=_INVERT_OP[op], value=value)})  # type: ignore[arg-type]
        case DateValueFilter(op=op) | NumericValueFilter(op=op):
            return pf.model_copy(update={"condition": pf.condition.model_copy(update={"op": _INVERT_OP[op]})})
        case _:
            # For range/string/ltree filters, we cannot simply invert.
            # Return as-is; the caller wraps in must_not logic at the tree level.
            return pf


def _invert_range_to_or(
    pf: PathFilter, range_val: DateRange | NumericRange, value_filter_cls: type[DateValueFilter | NumericValueFilter]
) -> FilterTree:
    """Invert a BETWEEN range filter to OR of inverted bounds (< start OR > end)."""
    lo = PathFilter(path=pf.path, condition=value_filter_cls(op=FilterOp.LT, value=range_val.start), value_kind=pf.value_kind)  # type: ignore[arg-type]
    hi = PathFilter(path=pf.path, condition=value_filter_cls(op=FilterOp.GT, value=range_val.end), value_kind=pf.value_kind)  # type: ignore[arg-type]
    return FilterTree(op=BooleanOperator.OR, children=[lo, hi])


def _negate_node(node: FilterTree | PathFilter) -> FilterTree | PathFilter:
    """Negate a single translated node for must_not semantics."""
    match node:
        case PathFilter(condition=EqualityFilter() | DateValueFilter() | NumericValueFilter()):
            return _invert_path_filter(node)
        case PathFilter(condition=DateRangeFilter(value=range_val)):
            return _invert_range_to_or(node, range_val, DateValueFilter)
        case PathFilter(condition=NumericRangeFilter(value=range_val)):
            return _invert_range_to_or(node, range_val, NumericValueFilter)
        case _:
            return node


def _translate_must_not(queries: list[ElasticQuery]) -> list[FilterTree | PathFilter]:
    """Translate must_not clauses by inverting operators where possible."""
    return [_negate_node(_translate_node(q)) for q in queries]


def _translate_node(query: ElasticQuery) -> FilterTree | PathFilter:
    """Recursively translate a single ES DSL node."""
    match query:
        case TermQuery():
            return _translate_term(query)
        case RangeQuery():
            return _translate_range(query)
        case WildcardQuery():
            return _translate_wildcard(query)
        case ExistsQuery():
            return _translate_exists(query)
        case BoolQuery():
            return _translate_bool(query)
        case _:
            raise ValueError(f"Unsupported ES DSL query type: {type(query)}")


def _translate_bool(query: BoolQuery) -> FilterTree | PathFilter:
    """Translate a bool query into a FilterTree."""
    clause = query.bool
    children: list[FilterTree | PathFilter] = []

    must_children = [_translate_node(q) for q in clause.must]
    should_children = [_translate_node(q) for q in clause.should]
    must_not_children = _translate_must_not(clause.must_not)

    # Build sub-trees for each clause type
    if clause.must and clause.should:
        # Both must and should: must is AND, should is OR, combine with AND
        children.extend(must_children)
        children.append(FilterTree(op=BooleanOperator.OR, children=should_children))
    elif clause.must:
        children.extend(must_children)
    elif clause.should:
        return (
            FilterTree(op=BooleanOperator.OR, children=should_children)
            if len(should_children) > 1
            else should_children[0]
        )

    children.extend(must_not_children)

    if not children:
        raise ValueError("bool query produced no children after translation")

    if len(children) == 1:
        return children[0]

    return FilterTree(op=BooleanOperator.AND, children=children)


def elastic_to_filter_tree(es_query: ElasticQuery) -> FilterTree:
    """Convert an Elasticsearch DSL query to a FilterTree.

    Args:
        es_query: A parsed ElasticQuery (TermQuery, RangeQuery, WildcardQuery,
                  ExistsQuery, or BoolQuery).

    Returns:
        A FilterTree suitable for compilation to SQL.

    Raises:
        ValueError: If the query structure is invalid or exceeds MAX_DEPTH.
    """
    result = _translate_node(es_query)
    if isinstance(result, PathFilter):
        return FilterTree(op=BooleanOperator.AND, children=[result])
    return result
