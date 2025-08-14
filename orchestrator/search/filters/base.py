from typing import Any, List, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.sql.elements import ColumnElement

from .date_filters import DateFilter
from .ltree_filters import LtreeFilter
from .numeric_filter import NumericFilter
from .operators import FilterOp


class EqualityFilter(BaseModel):
    op: Literal[FilterOp.EQ, FilterOp.NEQ]
    value: Any  # bool, str (UUID), str (enum values)

    def to_expression(self, column: ColumnElement, path: str) -> ColumnElement[bool]:
        str_value = str(self.value)
        match self.op:
            case FilterOp.EQ:
                return column == str_value
            case FilterOp.NEQ:
                return column != str_value


class StringFilter(BaseModel):
    op: Literal[FilterOp.EQ, FilterOp.NEQ, FilterOp.LIKE]
    value: str

    def to_expression(self, column: ColumnElement, path: str) -> ColumnElement[bool]:
        match self.op:
            case FilterOp.EQ:
                return column == self.value
            case FilterOp.NEQ:
                return column != self.value
            case FilterOp.LIKE:
                return column.like(self.value)

    @model_validator(mode="after")
    def validate_like_pattern(self) -> "StringFilter":
        """If the operation is 'like', the value must contain a wildcard."""
        if self.op == FilterOp.LIKE:
            if "%" not in self.value and "_" not in self.value:
                raise ValueError("The value for a 'like' operation must contain a wildcard character ('%' or '_').")
        return self


FilterCondition = Union[
    DateFilter,  # DATETIME
    NumericFilter,  # INT/FLOAT
    StringFilter,  # STRING TODO: convert to hybrid search
    EqualityFilter,  # BOOLEAN/UUID/BLOCK/RESOURCE_TYPE
    LtreeFilter,  # Path
]


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

    def to_expression(self, value_column: ColumnElement) -> ColumnElement[bool]:
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


FilterSet = List[PathFilter]
