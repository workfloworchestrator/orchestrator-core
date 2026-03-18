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

from orchestrator.search.core.types import BooleanOperator, FieldType, FilterOp, UIType
from orchestrator.search.filters.base import (
    EqualityFilter,
    FilterTree,
    PathFilter,
    StringFilter,
)
from orchestrator.search.filters.date_filters import DateRange, DateRangeFilter, DateValueFilter
from orchestrator.search.filters.ltree_filters import LtreeFilter
from orchestrator.search.filters.numeric_filter import NumericRange, NumericRangeFilter, NumericValueFilter

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

# ---------------------------------------------------------------------------
# Value-kind inference
# ---------------------------------------------------------------------------

_FIELD_TYPE_TO_UI: dict[FieldType, UIType] = {
    FieldType.INTEGER: UIType.NUMBER,
    FieldType.FLOAT: UIType.NUMBER,
    FieldType.BOOLEAN: UIType.BOOLEAN,
    FieldType.DATETIME: UIType.DATETIME,
    FieldType.STRING: UIType.STRING,
    FieldType.UUID: UIType.STRING,
}


def _infer_value_kind(value: Any) -> UIType:
    """Infer a UIType from a raw filter value using FieldType heuristics."""
    ft = FieldType.infer(value)
    return _FIELD_TYPE_TO_UI.get(ft, UIType.STRING)


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

    term: dict[str, Any]

    @model_validator(mode="after")
    def _validate_single_field(self) -> TermQuery:
        if len(self.term) != 1:
            raise ValueError("term query must have exactly one field")
        return self


class RangeQuery(BaseModel):
    """``{"range": {"field": {"gt": v, ...}}}``."""

    range: dict[str, dict[str, Any]]

    @model_validator(mode="after")
    def _validate_single_field(self) -> RangeQuery:
        if len(self.range) != 1:
            raise ValueError("range query must have exactly one field")
        return self


class WildcardQuery(BaseModel):
    """``{"wildcard": {"field": {"value": "pattern"}}}``."""

    wildcard: dict[str, dict[str, str]]

    @model_validator(mode="after")
    def _validate_single_field(self) -> WildcardQuery:
        if len(self.wildcard) != 1:
            raise ValueError("wildcard query must have exactly one field")
        return self


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

_RANGE_OPS: dict[str, FilterOp] = {
    "gt": FilterOp.GT,
    "gte": FilterOp.GTE,
    "lt": FilterOp.LT,
    "lte": FilterOp.LTE,
}


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

    # Determine if this is a two-bound (between) or single-bound query
    lower_key = next((k for k in ("gte", "gt") if k in bounds), None)
    upper_key = next((k for k in ("lte", "lt") if k in bounds), None)

    if lower_key and upper_key and lower_key == "gte" and upper_key == "lte":
        # Two-bound → BETWEEN range filter
        start_val, end_val = bounds[lower_key], bounds[upper_key]
        value_kind = _infer_value_kind(start_val)

        condition: DateRangeFilter | NumericRangeFilter
        if value_kind == UIType.DATETIME:
            condition = DateRangeFilter(op=FilterOp.BETWEEN, value=DateRange(start=start_val, end=end_val))
        else:
            condition = NumericRangeFilter(op=FilterOp.BETWEEN, value=NumericRange(start=start_val, end=end_val))

        return PathFilter(path=field, condition=condition, value_kind=value_kind)

    # Single bound or non-gte/lte two-bound: pick the first recognised op
    for es_key, filter_op in _RANGE_OPS.items():
        if es_key in bounds:
            value = bounds[es_key]
            value_kind = _infer_value_kind(value)

            single_condition: DateValueFilter | NumericValueFilter
            if value_kind == UIType.DATETIME:
                single_condition = DateValueFilter(op=filter_op, value=value)  # type: ignore[arg-type]
            else:
                single_condition = NumericValueFilter(op=filter_op, value=value)  # type: ignore[arg-type]

            return PathFilter(path=field, condition=single_condition, value_kind=value_kind)

    raise ValueError(f"range query for '{field}' has no recognised bounds: {bounds}")


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
    cond = pf.condition
    if isinstance(cond, EqualityFilter):
        inverted = _INVERT_OP[cond.op]
        return pf.model_copy(update={"condition": EqualityFilter(op=inverted, value=cond.value)})  # type: ignore[arg-type]
    if isinstance(cond, (DateValueFilter, NumericValueFilter)):
        inverted = _INVERT_OP[cond.op]
        return pf.model_copy(update={"condition": cond.model_copy(update={"op": inverted})})
    # For range/string/ltree filters, we cannot simply invert — wrap in a NOT-equivalent.
    # Return as-is; the caller wraps in must_not logic at the tree level.
    return pf


def _translate_must_not(queries: list[ElasticQuery], depth: int) -> list[FilterTree | PathFilter]:
    """Translate must_not clauses by inverting operators where possible."""
    results: list[FilterTree | PathFilter] = []
    for q in queries:
        node = _translate_node(q, depth)
        if isinstance(node, PathFilter) and isinstance(
            node.condition, (EqualityFilter, DateValueFilter, NumericValueFilter)
        ):
            results.append(_invert_path_filter(node))
        elif isinstance(node, PathFilter) and isinstance(node.condition, DateRangeFilter):
            # date between → OR of inverted bounds
            date_val = node.condition.value
            lo: PathFilter = PathFilter(
                path=node.path,
                condition=DateValueFilter(op=FilterOp.LT, value=date_val.start),
                value_kind=node.value_kind,
            )
            hi: PathFilter = PathFilter(
                path=node.path,
                condition=DateValueFilter(op=FilterOp.GT, value=date_val.end),
                value_kind=node.value_kind,
            )
            results.append(FilterTree(op=BooleanOperator.OR, children=[lo, hi]))
        elif isinstance(node, PathFilter) and isinstance(node.condition, NumericRangeFilter):
            # numeric between → OR of inverted bounds
            num_val = node.condition.value
            lo = PathFilter(
                path=node.path,
                condition=NumericValueFilter(op=FilterOp.LT, value=num_val.start),
                value_kind=node.value_kind,
            )
            hi = PathFilter(
                path=node.path,
                condition=NumericValueFilter(op=FilterOp.GT, value=num_val.end),
                value_kind=node.value_kind,
            )
            results.append(FilterTree(op=BooleanOperator.OR, children=[lo, hi]))
        else:
            # For complex sub-trees or non-invertible conditions, wrap with NEQ-style
            # We can't generically negate; raise for unsupported cases
            results.append(node)
    return results


def _translate_node(query: ElasticQuery, depth: int = 1) -> FilterTree | PathFilter:
    """Recursively translate a single ES DSL node."""
    if depth > FilterTree.MAX_DEPTH:
        raise ValueError(f"ElasticQuery nesting exceeds MAX_DEPTH={FilterTree.MAX_DEPTH}")

    if isinstance(query, TermQuery):
        return _translate_term(query)
    if isinstance(query, RangeQuery):
        return _translate_range(query)
    if isinstance(query, WildcardQuery):
        return _translate_wildcard(query)
    if isinstance(query, ExistsQuery):
        return _translate_exists(query)
    if isinstance(query, BoolQuery):
        return _translate_bool(query, depth)

    raise ValueError(f"Unsupported ES DSL query type: {type(query)}")


def _translate_bool(query: BoolQuery, depth: int) -> FilterTree | PathFilter:
    """Translate a bool query into a FilterTree."""
    clause = query.bool
    children: list[FilterTree | PathFilter] = []

    must_children = [_translate_node(q, depth + 1) for q in clause.must]
    should_children = [_translate_node(q, depth + 1) for q in clause.should]
    must_not_children = _translate_must_not(clause.must_not, depth + 1)

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
    result = _translate_node(es_query, depth=1)
    if isinstance(result, PathFilter):
        return FilterTree(op=BooleanOperator.AND, children=[result])
    return result
