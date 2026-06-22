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

from sqlalchemy import Select, and_, literal, or_, select
from sqlalchemy_utils import Ltree

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import SearchMetadata
from orchestrator.core.search.query.mixins import OrderDirection, StructuredOrderBy

from ..pagination import PageCursor
from .base import Retriever

ORDER_VALUE_LABEL = "order_value"


class StructuredRetriever(Retriever):
    """Applies a dummy score for purely structured searches with no text query."""

    def __init__(self, cursor: PageCursor | None, order_by: StructuredOrderBy | None = None) -> None:
        self.cursor = cursor
        self.order_by = order_by

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()

        if not self.order_by:
            # Default structured pagination is stable on entity_id only.
            stmt = select(cand.c.entity_id, cand.c.entity_title, literal(1.0).label("score")).select_from(cand)
            if self.cursor is not None:
                stmt = stmt.where(cand.c.entity_id > self.cursor.id)
            return stmt.order_by(cand.c.entity_id.asc())

        # Look up the requested indexed path value for each candidate entity.
        path_subquery = (
            select(AiSearchIndex.value)
            .where(
                AiSearchIndex.entity_id == cand.c.entity_id,
                AiSearchIndex.path == Ltree(self.order_by.element),
            )
            .correlate(cand)
        ).scalar_subquery()

        # Expose the computed sort value as order_value for filtering and ordering
        inner = select(
            cand.c.entity_id,
            cand.c.entity_title,
            literal(1.0).label("score"),
            path_subquery.label(ORDER_VALUE_LABEL),
        ).select_from(cand).subquery("ordered_cand")

        stmt = select(inner.c.entity_id, inner.c.entity_title, inner.c.score, inner.c.order_value).select_from(inner)

        if self.cursor is not None and self.cursor.order_value is not None:
            # Resume after the last sorted value, using entity_id (as deterministic tiebreaker) for rows with the same value
            tiebreak = and_(inner.c.order_value == self.cursor.order_value, inner.c.entity_id > self.cursor.id)
            if self.order_by.direction == OrderDirection.ASC:
                stmt = stmt.where(or_(inner.c.order_value > self.cursor.order_value, tiebreak))
            else:
                stmt = stmt.where(or_(inner.c.order_value < self.cursor.order_value, tiebreak))

        # Sort by entity_id too so rows with the same order_value stay in a stable / deterministic order.
        order_col = inner.c.order_value.asc() if self.order_by.direction == OrderDirection.ASC else inner.c.order_value.desc()
        return stmt.order_by(order_col, inner.c.entity_id.asc())

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.structured()
