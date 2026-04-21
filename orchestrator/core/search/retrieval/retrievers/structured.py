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

from sqlalchemy import Select, Subquery, literal, select
from sqlalchemy_utils import Ltree

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import SearchMetadata
from orchestrator.core.search.query.mixins import OrderDirection, StructuredOrderBy

from ..pagination import PageCursor
from .base import Retriever


def _apply_structured_ordering(stmt: Select, cand: Subquery, order_by: StructuredOrderBy | None = None) -> Select:
    if not order_by:
        return stmt.order_by(cand.c.entity_id.asc())

    path_subquery = (
        select(AiSearchIndex.value.label("order_value"))
        .where(AiSearchIndex.entity_id == cand.c.entity_id, AiSearchIndex.path == Ltree(order_by.element))
        .correlate(cand)
    ).scalar_subquery()

    _is_asc = order_by.direction == OrderDirection.ASC
    order_direction = path_subquery.asc() if _is_asc else path_subquery.desc()
    return stmt.order_by(order_direction)


class StructuredRetriever(Retriever):
    """Applies a dummy score for purely structured searches with no text query."""

    def __init__(self, cursor: PageCursor | None, order_by: StructuredOrderBy | None = None) -> None:
        self.cursor = cursor
        self.order_by = order_by

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()
        stmt = select(cand.c.entity_id, cand.c.entity_title, literal(1.0).label("score")).select_from(cand)

        if self.cursor is not None:
            stmt = stmt.where(cand.c.entity_id > self.cursor.id)

        return _apply_structured_ordering(stmt, cand, self.order_by)

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.structured()
