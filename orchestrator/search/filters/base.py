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

from __future__ import annotations

from itertools import count
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import BinaryExpression, and_, cast, exists, literal, or_, select
from sqlalchemy.dialects.postgresql import BOOLEAN
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.types import BooleanOperator, FieldType, FilterOp, SQLAColumn, UIType

from .date_filters import DateFilter
from .ltree_filters import LtreeFilter
from .numeric_filter import NumericFilter


class EqualityFilter(BaseModel):
    op: Literal[FilterOp.EQ, FilterOp.NEQ]
    value: Any

    def to_expression(self, column: SQLAColumn, path: str) -> BinaryExpression[bool] | ColumnElement[bool]:
        if isinstance(self.value, bool):
            colb = cast(column, BOOLEAN)
            return colb.is_(self.value) if self.op == FilterOp.EQ else ~colb.is_(self.value)
        sv = str(self.value)
        return (column == sv) if self.op == FilterOp.EQ else (column != sv)


class StringFilter(BaseModel):
    op: Literal[FilterOp.LIKE]
    value: str

    def to_expression(self, column: SQLAColumn, path: str) -> ColumnElement[bool]:
        return column.like(self.value)

    @model_validator(mode="after")
    def validate_like_pattern(self) -> StringFilter:
        """If the operation is 'like', the value must contain a wildcard."""
        if self.op == FilterOp.LIKE:
            if "%" not in self.value and "_" not in self.value:
                raise ValueError("The value for a 'like' operation must contain a wildcard character ('%' or '_').")
        return self


# Order matters! Ambiguous ops (like 'eq') are resolved by first matching filter
FilterCondition = (
    DateFilter  # DATETIME
    | NumericFilter  # INT/FLOAT
    | StringFilter  # STRING TODO: convert to hybrid search?
    | LtreeFilter  # Path
    | EqualityFilter  # BOOLEAN/UUID/BLOCK/RESOURCE_TYPE - most generic, try last
)


class PathFilter(BaseModel):

    path: str = Field(description="The ltree path of the field to filter on, e.g., 'subscription.customer_id'.")
    condition: FilterCondition = Field(description="The filter condition to apply.")

    value_kind: UIType

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"path": "subscription.status", "condition": {"op": "eq", "value": "active"}, "value_kind": "string"},
                {
                    "path": "subscription.customer_id",
                    "condition": {"op": "neq", "value": "acme"},
                    "value_kind": "string",
                },
                {
                    "path": "subscription.start_date",
                    "condition": {"op": "gt", "value": "2025-01-01"},
                    "value_kind": "datetime",
                },
                {
                    "path": "subscription.end_date",
                    "condition": {
                        "op": "between",
                        "value": {"start": "2025-06-01", "end": "2025-07-01"},
                    },
                    "value_kind": "datetime",
                },
                {
                    "path": "subscription",
                    "condition": {"op": "has_component", "value": "node"},
                    "value_kind": "component",
                },
            ]
        }
    )

    @model_validator(mode="before")
    @classmethod
    def _transfer_path_to_value_if_needed(cls, data: Any) -> Any:
        """Transform for path-only filters.

        If `op` is `has_component`, `not_has_component`, or `ends_with` and no `value` is
        provided in the `condition`, this validator will automatically use the `path`
        field as the `value` and set the `path` to a wildcard '*' for the query.
        """
        if isinstance(data, dict):
            path = data.get("path")
            condition = data.get("condition")

            if path and isinstance(condition, dict):
                op = condition.get("op")
                value = condition.get("value")

                path_only_ops = [FilterOp.HAS_COMPONENT, FilterOp.NOT_HAS_COMPONENT, FilterOp.ENDS_WITH]

                if op in path_only_ops and value is None:
                    condition["value"] = path
                    data["path"] = "*"
        return data

    def to_expression(self, value_column: SQLAColumn, value_type_column: SQLAColumn) -> ColumnElement[bool]:
        """Convert the path filter into a SQLAlchemy expression with type safety.

        This method creates a type guard to ensure we only match compatible field types,
        then delegates to the specific filter condition.

        Args:
            value_column (ColumnElement): The SQLAlchemy column element representing the value to be filtered.
            value_type_column (ColumnElement): The SQLAlchemy column element representing the field type.

        Returns:
            ColumnElement[bool]: A SQLAlchemy boolean expression that can be used in a ``WHERE`` clause.
        """

        # Type guard - only match compatible field types
        allowed_field_types = [ft.value for ft in FieldType if UIType.from_field_type(ft) == self.value_kind]
        type_guard = value_type_column.in_(allowed_field_types) if allowed_field_types else literal(True)

        return and_(type_guard, self.condition.to_expression(value_column, self.path))


class FilterTree(BaseModel):
    op: BooleanOperator = Field(
        description="Operator for grouping conditions in uppercase.", default=BooleanOperator.AND
    )

    children: list[FilterTree | PathFilter] = Field(min_length=1, description="Path filters or nested groups.")

    MAX_DEPTH: ClassVar[int] = 5

    model_config = ConfigDict(
        json_schema_extra={
            "description": (
                "Boolean filter tree. Operators must be UPPERCASE: AND / OR.\n"
                "Node shapes:\n"
                "  • Group: {'op':'AND'|'OR', 'children': [<PathFilter|FilterTree>, ...]}\n"
                "  • Leaf (PathFilter): {'path':'<ltree>', 'condition': {...}}\n"
                "Rules:\n"
                "  • Do NOT put 'op' or 'children' inside a leaf 'condition'.\n"
                f"  • Max depth = {MAX_DEPTH}.\n"
            ),
            "examples": [
                {
                    "description": "Simple filters",
                    "op": "AND",
                    "children": [
                        {"path": "subscription.status", "condition": {"op": "eq", "value": "active"}},
                        {"path": "subscription.start_date", "condition": {"op": "gt", "value": "2021-01-01"}},
                    ],
                },
                {
                    "description": "Complex filters with OR group",
                    "op": "AND",
                    "children": [
                        {"path": "subscription.start_date", "condition": {"op": "gte", "value": "2024-01-01"}},
                        {
                            "op": "OR",
                            "children": [
                                {"path": "subscription.product.name", "condition": {"op": "like", "value": "%fiber%"}},
                                {"path": "subscription.customer_id", "condition": {"op": "eq", "value": "Surf"}},
                            ],
                        },
                    ],
                },
            ],
        }
    )

    @model_validator(mode="after")
    def _validate_depth(self) -> FilterTree:
        def depth(node: "FilterTree | PathFilter") -> int:
            return 1 + max(depth(c) for c in node.children) if isinstance(node, FilterTree) else 1

        if depth(self) > self.MAX_DEPTH:
            raise ValueError(f"FilterTree nesting exceeds MAX_DEPTH={self.MAX_DEPTH}")
        return self

    @classmethod
    def from_flat_and(cls, filters: list[PathFilter]) -> FilterTree | None:
        """Wrap a flat list of PathFilter into an AND group (or None)."""
        return None if not filters else cls(op=BooleanOperator.AND, children=list(filters))

    def get_all_paths(self) -> set[str]:
        """Collects all unique paths from the PathFilter leaves in the tree."""
        return {leaf.path for leaf in self.get_all_leaves()}

    def get_all_leaves(self) -> list[PathFilter]:
        """Collect all PathFilter leaves in the tree."""
        leaves: list[PathFilter] = []
        for child in self.children:
            if isinstance(child, PathFilter):
                leaves.append(child)
            else:
                leaves.extend(child.get_all_leaves())
        return leaves

    def to_expression(
        self,
        entity_id_col: SQLAColumn,
        *,
        entity_type_value: str | None = None,
    ) -> ColumnElement[bool]:
        """Compile this tree into a SQLAlchemy boolean expression.

        Args:
            entity_id_col (SQLAColumn): Column in the outer query representing the entity ID.
            entity_type_value (str, optional): If provided, each subquery is additionally constrained to this entity type.

        Returns:
            ColumnElement[bool]: A SQLAlchemy expression suitable for use in a WHERE clause.
        """

        alias_idx = count(1)

        def leaf_exists(pf: PathFilter) -> ColumnElement[bool]:
            from sqlalchemy.orm import aliased

            alias = aliased(AiSearchIndex, name=f"flt_{next(alias_idx)}")

            correlates = [alias.entity_id == entity_id_col]
            if entity_type_value is not None:
                correlates.append(alias.entity_type == entity_type_value)

            if isinstance(pf.condition, LtreeFilter):
                # row-level predicate is always positive
                positive = pf.condition.to_expression(alias.path, pf.path)
                subq = select(1).select_from(alias).where(and_(*correlates, positive))
                if pf.condition.op == FilterOp.NOT_HAS_COMPONENT:
                    return ~exists(subq)  # NOT at the entity level
                return exists(subq)

            # value leaf: path predicate + typed value compare
            if "." not in pf.path:
                path_pred = LtreeFilter(op=FilterOp.ENDS_WITH, value=pf.path).to_expression(alias.path, "")
            else:
                path_pred = alias.path == Ltree(pf.path)

            value_pred = pf.to_expression(alias.value, alias.value_type)
            subq = select(1).select_from(alias).where(and_(*correlates, path_pred, value_pred))
            return exists(subq)

        def compile_node(node: FilterTree | PathFilter) -> ColumnElement[bool]:
            if isinstance(node, FilterTree):
                compiled = [compile_node(ch) for ch in node.children]
                return and_(*compiled) if node.op == BooleanOperator.AND else or_(*compiled)
            return leaf_exists(node)

        return compile_node(self)
