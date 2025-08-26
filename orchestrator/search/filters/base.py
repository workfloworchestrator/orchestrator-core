from __future__ import annotations

from itertools import count
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.types import BooleanOperator, FilterOp, SQLAColumn

from .date_filters import DateFilter
from .ltree_filters import LtreeFilter
from .numeric_filter import NumericFilter


class EqualityFilter(BaseModel):
    op: Literal[FilterOp.EQ, FilterOp.NEQ]
    value: Any  # bool, str (UUID), str (enum values)

    def to_expression(self, column: SQLAColumn, path: str) -> ColumnElement[bool]:
        str_value = str(self.value)
        match self.op:
            case FilterOp.EQ:
                return column == str_value
            case FilterOp.NEQ:
                return column != str_value


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


FilterCondition = (
    DateFilter  # DATETIME
    | NumericFilter  # INT/FLOAT
    | EqualityFilter  # BOOLEAN/UUID/BLOCK/RESOURCE_TYPE
    | StringFilter  # STRING TODO: convert to hybrid search
    | LtreeFilter  # Path
)


class PathFilter(BaseModel):

    path: str = Field(description="The ltree path of the field to filter on, e.g., 'subscription.customer_id'.")
    condition: FilterCondition = Field(description="The filter condition to apply.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "path": "subscription.status",
                    "condition": {"op": "eq", "value": "active"},
                },
                {
                    "path": "subscription.customer_id",
                    "condition": {"op": "ne", "value": "acme"},
                },
                {
                    "path": "subscription.start_date",
                    "condition": {"op": "gt", "value": "2025-01-01"},
                },
                {
                    "path": "subscription.end_date",
                    "condition": {
                        "op": "between",
                        "value": {"from": "2025-06-01", "to": "2025-07-01"},
                    },
                },
                {
                    "path": "subscription.*.name",
                    "condition": {"op": "matches_lquery", "value": "*.foo_*"},
                },
            ]
        }
    )

    def to_expression(self, value_column: SQLAColumn) -> ColumnElement[bool]:
        """Convert the path filter into a SQLAlchemy expression.

        This method delegates to the specific filter condition's ``to_expression``
        implementation, passing along the column and path for context.

        Parameters
        ----------
        value_column : ColumnElement
            The SQLAlchemy column element representing the value to be filtered.

        Returns:
        -------
        ColumnElement[bool]
            A SQLAlchemy boolean expression that can be used in a ``WHERE`` clause.
        """
        return self.condition.to_expression(value_column, self.path)


class FilterTree(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "description": (
                "Boolean filter tree. Operators must be UPPERCASE: AND / OR.\n"
                "Node shapes:\n"
                "  • Group: {'op':'AND'|'OR', 'children': [<PathFilter|FilterTree>, ...]}\n"
                "  • Leaf (PathFilter): {'path':'<ltree>', 'condition': {...}}\n"
                "Rules:\n"
                "  • Do NOT put 'op' or 'children' inside a leaf 'condition'.\n"
                "  • Max depth = 5.\n"
                "  • Use from_flat_and() for a flat list of leaves."
            ),
            "examples": [
                {
                    "op": "AND",
                    "children": [
                        {"path": "subscription.status", "condition": {"op": "eq", "value": "active"}},
                        {"path": "subscription.start_date", "condition": {"op": "gt", "value": "2021-01-01"}},
                    ],
                },
                {
                    "op": "AND",
                    "children": [
                        {"path": "subscription.start_date", "condition": {"op": "gte", "value": "2024-01-01"}},
                        {
                            "op": "OR",
                            "children": [
                                {"path": "subscription.product_name", "condition": {"op": "like", "value": "%fiber%"}},
                                {"path": "subscription.customer_id", "condition": {"op": "eq", "value": "Surf"}},
                            ],
                        },
                    ],
                },
            ],
        }
    )

    op: BooleanOperator = Field(
        description="Operator for grouping conditions in uppercase.", default=BooleanOperator.AND
    )

    children: list[FilterTree | PathFilter] = Field(min_length=1, description="Path filters or nested groups.")

    MAX_DEPTH: ClassVar[int] = 5

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

        Parameters
        ----------
        entity_id_col : SQLAColumn
            Column in the outer query representing the entity ID.
        entity_type_value : str, optional
            If provided, each subquery is additionally constrained to this entity type.

        Returns:
        -------
        ColumnElement[bool]
            A SQLAlchemy expression suitable for use in a WHERE clause.
        """
        alias_idx = count(1)

        def leaf_exists(pf: PathFilter) -> ColumnElement[bool]:
            from sqlalchemy.orm import aliased

            alias = aliased(AiSearchIndex, name=f"flt_{next(alias_idx)}")

            correlates = [alias.entity_id == entity_id_col]
            if entity_type_value is not None:
                correlates.append(alias.entity_type == entity_type_value)

            if isinstance(pf.condition, LtreeFilter):
                # Path-only condition acts on path column
                pred = pf.condition.to_expression(alias.path, pf.path)
                where_clause = and_(*correlates, pred)
            else:
                where_clause = and_(
                    *correlates,
                    alias.path == Ltree(pf.path),
                    pf.condition.to_expression(alias.value, pf.path),
                )

            subq = select(1).select_from(alias).where(where_clause)
            return exists(subq)

        def compile_node(node: FilterTree | PathFilter) -> ColumnElement[bool]:
            if isinstance(node, FilterTree):
                compiled = [compile_node(ch) for ch in node.children]
                return and_(*compiled) if node.op == BooleanOperator.AND else or_(*compiled)
            return leaf_exists(node)

        return compile_node(self)
