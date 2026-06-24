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

from sqlalchemy import Select, Subquery, and_, literal, or_, select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy_utils import Ltree

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import SearchMetadata
from orchestrator.core.search.query.mixins import OrderDirection, StructuredOrderBy

from ..pagination import PageCursor
from .base import Retriever

ORDER_VALUE_LABEL = "order_value"


def _apply_id_pagination(stmt: Select, cand: Subquery, cursor: PageCursor | None) -> Select:
    """Apply keyset pagination and stable ordering on entity_id alone (no order_by)."""
    if cursor is not None:
        stmt = stmt.where(cand.c.entity_id > cursor.id)
    return stmt.order_by(cand.c.entity_id.asc())


def _build_order_value_subquery(cand: Subquery, order_by: StructuredOrderBy) -> Subquery:
    """Materialise the EAV sort-field value as order_value so filtering and ordering share the same column.

    Uses a correlated subquery per row; acceptable for EAV — upgrade to lateral join if throughput requires it.
    """
    # Look up the requested indexed path value for each candidate entity.
    path_subquery = (
        select(AiSearchIndex.value)
        .where(
            AiSearchIndex.entity_id == cand.c.entity_id,
            AiSearchIndex.path == Ltree(order_by.element),
        )
        .correlate(cand)
    ).scalar_subquery()

    # Expose the computed sort value as order_value so pagination can filter on the same column.
    return select(
        cand.c.entity_id,
        cand.c.entity_title,
        literal(1.0).label("score"),
        path_subquery.label(ORDER_VALUE_LABEL),
    ).select_from(cand).subquery("ordered_cand")


def _apply_order_value_pagination(stmt: Select, inner: Subquery, cursor: PageCursor | None, order_by: StructuredOrderBy) -> Select:
    """Apply keyset pagination and ordering on order_value, using entity_id as a deterministic tiebreaker."""
    if cursor is not None and cursor.order_value is not None:
        # Resume after the last sorted value; entity_id breaks ties for rows with the same order_value.
        tiebreak = and_(inner.c.order_value == cursor.order_value, inner.c.entity_id > cursor.id)
        if order_by.direction == OrderDirection.ASC:
            stmt = stmt.where(or_(inner.c.order_value > cursor.order_value, tiebreak))
        else:
            stmt = stmt.where(or_(inner.c.order_value < cursor.order_value, tiebreak))

    # entity_id as secondary sort keeps pages stable when multiple rows share the same order_value.
    order_col: ColumnElement = inner.c.order_value.asc() if order_by.direction == OrderDirection.ASC else inner.c.order_value.desc()
    return stmt.order_by(order_col, inner.c.entity_id.asc())


class StructuredRetriever(Retriever):
    """Applies a dummy score for purely structured searches with no text query."""

    def __init__(self, cursor: PageCursor | None, order_by: StructuredOrderBy | None = None) -> None:
        self.cursor = cursor
        self.order_by = order_by

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()

        if not self.order_by:
            stmt = select(cand.c.entity_id, cand.c.entity_title, literal(1.0).label("score")).select_from(cand)
            return _apply_id_pagination(stmt, cand, self.cursor)

        inner = _build_order_value_subquery(cand, self.order_by)
        stmt = select(inner.c.entity_id, inner.c.entity_title, inner.c.score, inner.c.order_value).select_from(inner)
        return _apply_order_value_pagination(stmt, inner, self.cursor, self.order_by)

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.structured()
