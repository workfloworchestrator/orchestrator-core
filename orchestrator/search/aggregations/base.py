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

from abc import abstractmethod
from enum import Enum
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Integer, cast, func
from sqlalchemy.sql.elements import ColumnElement, Label


class AggregationType(str, Enum):
    """Types of aggregations that can be computed."""

    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"


class TemporalPeriod(str, Enum):
    """Time periods for temporal grouping."""

    YEAR = "year"
    QUARTER = "quarter"
    MONTH = "month"
    WEEK = "week"
    DAY = "day"
    HOUR = "hour"


class TemporalGrouping(BaseModel):
    """Defines temporal grouping for date/time fields.

    Used to group query results by time periods (e.g., group subscriptions by start_date per month).
    """

    field: str = Field(description="The datetime field path to group by temporally.")
    period: TemporalPeriod = Field(description="The time period to group by (year, quarter, month, week, day, hour).")

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"field": "subscription.start_date", "period": "month"},
                {"field": "subscription.end_date", "period": "year"},
                {"field": "process.created_at", "period": "day"},
            ]
        },
    )

    def get_pivot_fields(self) -> list[str]:
        """Return fields that need to be pivoted for this temporal grouping."""
        return [self.field]

    def to_expression(self, pivot_cte_columns: Any) -> tuple[Label, Any, str]:
        """Build SQLAlchemy expression for temporal grouping.

        Args:
            pivot_cte_columns: The columns object from the pivot CTE

        Returns:
            tuple: (select_column, group_by_column, column_name)
                - select_column: Labeled column for SELECT
                - group_by_column: Column expression for GROUP BY
                - column_name: The label/name of the column in results
        """
        from sqlalchemy import TIMESTAMP, cast, func

        field_alias = BaseAggregation.field_to_alias(self.field)
        col = getattr(pivot_cte_columns, field_alias)
        truncated_col = func.date_trunc(self.period.value, cast(col, TIMESTAMP(timezone=True)))

        # Column name without prefix
        col_name = f"{field_alias}_{self.period.value}"
        select_col = truncated_col.label(col_name)
        return select_col, truncated_col, col_name


class BaseAggregation(BaseModel):
    """Base class for all aggregation types."""

    type: AggregationType = Field(description="The type of aggregation to perform.")
    alias: str = Field(description="The name for this aggregation in the results.")

    @classmethod
    def create(cls, data: dict) -> "Aggregation":
        """Create the correct aggregation instance based on type field.

        Args:
            data: Dictionary with aggregation data including 'type' discriminator

        Returns:
            Validated aggregation instance (CountAggregation or FieldAggregation)

        Raises:
            ValidationError: If data is invalid or type is unknown
        """
        from pydantic import TypeAdapter

        adapter: TypeAdapter = TypeAdapter(Aggregation)
        return adapter.validate_python(data)

    @staticmethod
    def field_to_alias(field_path: str) -> str:
        """Convert field path to SQL column alias.

        Examples:
            'subscription.name' -> 'subscription_name'
            'product.serial-number' -> 'product_serial_number'
        """
        return field_path.replace(".", "_").replace("-", "_")

    def get_pivot_fields(self) -> list[str]:
        """Return fields that need to be pivoted for this aggregation."""
        return []

    @abstractmethod
    def to_expression(self, *args: Any, **kwargs: Any) -> Label:
        """Build SQLAlchemy expression for this aggregation.

        Returns:
            Label: A labeled SQLAlchemy expression
        """
        raise NotImplementedError


class CountAggregation(BaseAggregation):
    """Count aggregation - counts number of entities."""

    type: Literal[AggregationType.COUNT]

    def to_expression(self, entity_id_column: ColumnElement) -> Label:
        """Build SQLAlchemy expression for count aggregation.

        Args:
            entity_id_column: The entity_id column from the pivot CTE

        Returns:
            Label: A labeled SQLAlchemy expression
        """
        return func.count(entity_id_column).label(self.alias)


class FieldAggregation(BaseAggregation):
    """Field-based aggregation (sum, avg, min, max)."""

    type: Literal[AggregationType.SUM, AggregationType.AVG, AggregationType.MIN, AggregationType.MAX]
    field: str = Field(description="The field path to aggregate on.")

    def get_pivot_fields(self) -> list[str]:
        """Return fields that need to be pivoted for this aggregation."""
        return [self.field]

    def to_expression(self, pivot_cte_columns: Any) -> Label:
        """Build SQLAlchemy expression for field-based aggregation.

        Args:
            pivot_cte_columns: The columns object from the pivot CTE

        Returns:
            Label: A labeled SQLAlchemy expression

        Raises:
            ValueError: If the field is not found in the pivot CTE
        """
        field_alias = self.field_to_alias(self.field)

        if not hasattr(pivot_cte_columns, field_alias):
            raise ValueError(f"Field '{self.field}' (alias: '{field_alias}') not found in pivot CTE columns")

        col = getattr(pivot_cte_columns, field_alias)

        numeric_col = cast(col, Integer)

        match self.type:
            case AggregationType.SUM:
                return func.sum(numeric_col).label(self.alias)
            case AggregationType.AVG:
                return func.avg(numeric_col).label(self.alias)
            case AggregationType.MIN:
                return func.min(numeric_col).label(self.alias)
            case AggregationType.MAX:
                return func.max(numeric_col).label(self.alias)
            case _:
                raise ValueError(f"Unsupported aggregation type: {self.type}")


Aggregation: TypeAlias = Annotated[CountAggregation | FieldAggregation, Field(discriminator="type")]
