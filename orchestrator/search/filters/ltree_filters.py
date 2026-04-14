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

from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import bindparam, cast
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.types import UserDefinedType
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.search.core.types import LTREE_SEPARATOR, FilterOp, SQLAColumn


class _LQuery(UserDefinedType):
    """PostgreSQL lquery type; ensures bindparams are cast to lquery, not varchar."""

    cache_ok = True

    def get_col_spec(self, **_kw: Any) -> str:
        return "lquery"

    def bind_expression(self, bindvalue: Any) -> Any:
        return cast(bindvalue, self)


class LtreeFilter(BaseModel):
    """Filter for ltree path operations."""

    op: Literal[
        FilterOp.MATCHES_LQUERY,
        FilterOp.IS_ANCESTOR,
        FilterOp.IS_DESCENDANT,
        FilterOp.PATH_MATCH,
        FilterOp.HAS_COMPONENT,
        FilterOp.NOT_HAS_COMPONENT,
        FilterOp.ENDS_WITH,
    ]
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
                param = bindparam(None, self.value, type_=_LQuery())
                return column.op("~")(param)
            case FilterOp.PATH_MATCH:
                ltree_value = Ltree(path)
                return column == ltree_value
            case FilterOp.HAS_COMPONENT | FilterOp.NOT_HAS_COMPONENT:
                return column.op("~")(
                    bindparam(None, f"*{LTREE_SEPARATOR}{self.value}{LTREE_SEPARATOR}*", type_=_LQuery())
                )
            case FilterOp.ENDS_WITH:
                return column.op("~")(bindparam(None, f"*{LTREE_SEPARATOR}{self.value}", type_=_LQuery()))
