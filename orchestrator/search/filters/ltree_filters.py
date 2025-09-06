from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import TEXT, bindparam
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.search.core.types import FilterOp, SQLAColumn


class LtreeFilter(BaseModel):
    """Filter for ltree path operations."""

    op: Literal[FilterOp.MATCHES_LQUERY, FilterOp.IS_ANCESTOR, FilterOp.IS_DESCENDANT, FilterOp.PATH_MATCH]
    value: str = Field(description="The ltree path or lquery pattern to compare against.")

    def to_expression(self, column: SQLAColumn, path: str) -> ColumnElement[bool]:
        """Converts the filter condition into a SQLAlchemy expression."""
        match self.op:
            case FilterOp.IS_DESCENDANT:
                ltree_value = Ltree(self.value)
                return column.op("<@")(ltree_value)
            case FilterOp.IS_ANCESTOR:
                ltree_value = Ltree(self.value)
                return column.op("@>")(ltree_value)
            case FilterOp.MATCHES_LQUERY:
                param = bindparam("lquery_pattern", self.value, type_=TEXT)
                return column.op("~")(param)
            case FilterOp.PATH_MATCH:
                ltree_value = Ltree(path)
                return column == ltree_value
