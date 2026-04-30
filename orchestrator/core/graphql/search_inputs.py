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

"""Strawberry GraphQL input types that mirror Pydantic search filter models.

GraphQL does not support union input types, so we flatten FilterCondition
(DateFilter | NumericFilter | StringFilter | LtreeFilter | EqualityFilter)
into a single FilterConditionInput with optional fields and dispatch to the
correct Pydantic model via to_pydantic().

SearchInput.to_select_query(entity_type) builds a SelectQuery; entity_type is
supplied by the resolver rather than stored as a GraphQL field.
"""

import strawberry

from orchestrator.core.search.core.types import (
    BooleanOperator,
    EntityType,
    FilterOp,
    RetrieverType,
    UIType,
)
from orchestrator.core.search.filters.base import (
    EqualityFilter,
    FilterTree,
    PathFilter,
    StringFilter,
)
from orchestrator.core.search.filters.date_filters import DateRange, DateRangeFilter, DateValueFilter
from orchestrator.core.search.filters.ltree_filters import LtreeFilter
from orchestrator.core.search.filters.numeric_filter import NumericRange, NumericRangeFilter, NumericValueFilter
from orchestrator.core.search.query.mixins import OrderDirection, StructuredOrderBy
from orchestrator.core.search.query.queries import SelectQuery

FilterOpEnum = strawberry.enum(FilterOp, name="FilterOp")
BooleanOperatorEnum = strawberry.enum(BooleanOperator, name="BooleanOperator")
EntityTypeEnum = strawberry.enum(EntityType, name="EntityType")
RetrieverTypeEnum = strawberry.enum(RetrieverType, name="RetrieverType")
UITypeEnum = strawberry.enum(UIType, name="UIType")
OrderDirectionEnum = strawberry.enum(OrderDirection, name="OrderDirection")

# Ltree-specific ops for dispatch
_LTREE_OPS = frozenset(
    {
        FilterOp.MATCHES_LQUERY,
        FilterOp.IS_ANCESTOR,
        FilterOp.IS_DESCENDANT,
        FilterOp.PATH_MATCH,
        FilterOp.HAS_COMPONENT,
        FilterOp.NOT_HAS_COMPONENT,
        FilterOp.ENDS_WITH,
    }
)

_COMPARISON_OPS = frozenset({FilterOp.LT, FilterOp.LTE, FilterOp.GT, FilterOp.GTE})


@strawberry.input(description="Flattened filter condition. Provide fields relevant to the chosen op.")
class FilterConditionInput:
    op: FilterOpEnum  # type: ignore[valid-type]
    value: str | None = None
    range_start: str | None = None
    range_end: str | None = None

    def to_pydantic(
        self, value_kind: UIType = UIType.STRING
    ) -> (
        EqualityFilter
        | StringFilter
        | DateValueFilter
        | DateRangeFilter
        | NumericValueFilter
        | NumericRangeFilter
        | LtreeFilter
    ):
        """Dispatch to the correct Pydantic filter model based on op and value_kind."""
        match (self.op, value_kind):
            case (op, _) if op in _LTREE_OPS:
                return LtreeFilter(op=op, value=self.value or "")
            case (FilterOp.LIKE, _):
                return StringFilter(op=FilterOp.LIKE, value=self.value or "")
            case (FilterOp.BETWEEN, UIType.DATETIME):
                return DateRangeFilter(
                    op=FilterOp.BETWEEN,
                    value=DateRange(start=self.range_start or "", end=self.range_end or ""),
                )
            case (FilterOp.BETWEEN, _):
                return NumericRangeFilter(
                    op=FilterOp.BETWEEN,
                    value=NumericRange(start=float(self.range_start or 0), end=float(self.range_end or 0)),
                )
            case (op, UIType.DATETIME) if op in _COMPARISON_OPS:
                return DateValueFilter(op=op, value=self.value or "")
            case (op, UIType.NUMBER) if op in _COMPARISON_OPS:
                return NumericValueFilter(op=op, value=float(self.value or 0))
            case (op, _) if op in _COMPARISON_OPS:
                raise ValueError(f"Operator {op!r} is not valid for value_kind={value_kind!r}")
            case _:
                return EqualityFilter(op=self.op, value=self.value)


@strawberry.input(description="A filter on a specific field path.")
class PathFilterInput:
    path: str
    condition: FilterConditionInput
    value_kind: UITypeEnum  # type: ignore[valid-type]

    def to_pydantic(self) -> PathFilter:
        return PathFilter(
            path=self.path,
            condition=self.condition.to_pydantic(value_kind=self.value_kind),
            value_kind=self.value_kind,
        )


@strawberry.input(description="Boolean filter tree with AND/OR grouping.")
class FilterTreeInput:
    op: BooleanOperatorEnum = BooleanOperator.AND  # type: ignore[valid-type]
    filters: list[PathFilterInput] = strawberry.field(default_factory=list)
    groups: list["FilterTreeInput"] = strawberry.field(default_factory=list)

    def to_pydantic(self) -> FilterTree:
        nodes: list[PathFilterInput | FilterTreeInput] = [*self.filters, *self.groups]
        children = [node.to_pydantic() for node in nodes]
        if not children:
            raise ValueError("FilterTreeInput must contain at least one filter or group")
        return FilterTree(op=self.op, children=children)


@strawberry.input(description="Ordering element for structured search results.")
class StructuredOrderByInput:
    element: str
    direction: OrderDirectionEnum = OrderDirection.ASC  # type: ignore[valid-type]

    def to_pydantic(self) -> StructuredOrderBy:
        return StructuredOrderBy(element=self.element, direction=self.direction)


@strawberry.input(description="Top-level search input for GraphQL queries.")
class SearchInput:
    query: str | None = None
    filters: FilterTreeInput | None = None
    limit: int = 10
    retriever: RetrieverTypeEnum | None = None  # type: ignore[valid-type]
    order_by: StructuredOrderByInput | None = None
    response_columns: list[str] | None = None

    def to_select_query(self, entity_type: EntityType) -> SelectQuery:
        return SelectQuery(
            entity_type=entity_type,
            query_text=self.query,
            filters=self.filters.to_pydantic() if self.filters else None,
            limit=self.limit,
            retriever=self.retriever,
            order_by=self.order_by.to_pydantic() if self.order_by else None,
            response_columns=self.response_columns,
        )
