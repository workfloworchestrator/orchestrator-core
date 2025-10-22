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

from sqlalchemy import Select, literal, select

from orchestrator.search.core.types import SearchMetadata

from ..pagination import PageCursor
from .base import Retriever


class StructuredRetriever(Retriever):
    """Applies a dummy score for purely structured searches with no text query."""

    def __init__(self, cursor: PageCursor | None) -> None:
        self.cursor = cursor

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()
        stmt = select(cand.c.entity_id, cand.c.entity_title, literal(1.0).label("score")).select_from(cand)

        if self.cursor is not None:
            stmt = stmt.where(cand.c.entity_id > self.cursor.id)

        return stmt.order_by(cand.c.entity_id.asc())

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.structured()
