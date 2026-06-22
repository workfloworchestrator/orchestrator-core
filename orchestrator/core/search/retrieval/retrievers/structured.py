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
from sqlalchemy.sql.selectable import ScalarSelect
from sqlalchemy_utils import Ltree

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import SearchMetadata
from orchestrator.core.search.query.mixins import OrderDirection, StructuredOrderBy

from ..pagination import PageCursor
from .base import Retriever


def _order_value_subquery(cand: Subquery, order_by: StructuredOrderBy) -> "ScalarSelect[str | None]":
    return (
        select(AiSearchIndex.value)
        .where(AiSearchIndex.entity_id == cand.c.entity_id, AiSearchIndex.path == Ltree(order_by.element))
        .correlate(cand)
    ).scalar_subquery()


class StructuredRetriever(Retriever):
    """Applies a dummy score for purely structured searches with no text query."""

    def __init__(self, cursor: PageCursor | None, order_by: StructuredOrderBy | None = None) -> None:
        self.cursor = cursor
        self.order_by = order_by

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()

        if not self.order_by:
            stmt = select(cand.c.entity_id, cand.c.entity_title, literal(1.0).label("score")).select_from(cand)
            if self.cursor is not None:
                stmt = stmt.where(cand.c.entity_id > self.cursor.id)
            return stmt.order_by(cand.c.entity_id.asc())

        order_subq = _order_value_subquery(cand, self.order_by)
        stmt = select(
            cand.c.entity_id,
            cand.c.entity_title,
            literal(1.0).label("score"),
            order_subq.label("order_value"),
        ).select_from(cand)

        if self.cursor is not None:
            if self.cursor.order_value is not None:
                _is_asc = self.order_by.direction == OrderDirection.ASC
                eq_tiebreak = and_(order_subq == self.cursor.order_value, cand.c.entity_id > self.cursor.id)
                page_condition = (
                    or_(order_subq > self.cursor.order_value, eq_tiebreak)
                    if _is_asc
                    else or_(order_subq < self.cursor.order_value, eq_tiebreak)
                )
                stmt = stmt.where(page_condition)
            else:
                # ponytail: backward compat for cursors created before order_value was added
                stmt = stmt.where(cand.c.entity_id > self.cursor.id)

        _is_asc = self.order_by.direction == OrderDirection.ASC
        order_direction = order_subq.asc() if _is_asc else order_subq.desc()
        return stmt.order_by(order_direction, cand.c.entity_id.asc())

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.structured()
