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

from sqlalchemy import Select, and_, cast, func, literal, or_, select
from sqlalchemy.sql.expression import ColumnElement

from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.types import SearchMetadata

from ..pagination import PageCursor
from .base import Retriever


class FuzzyRetriever(Retriever):
    """Ranks results based on the max of fuzzy text similarity scores."""

    def __init__(self, fuzzy_term: str, cursor: PageCursor | None) -> None:
        self.fuzzy_term = fuzzy_term
        self.cursor = cursor

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()

        similarity_expr = func.word_similarity(self.fuzzy_term, AiSearchIndex.value)

        raw_max = func.max(similarity_expr).over(partition_by=AiSearchIndex.entity_id)
        score = cast(
            func.round(cast(raw_max, self.SCORE_NUMERIC_TYPE), self.SCORE_PRECISION), self.SCORE_NUMERIC_TYPE
        ).label(self.SCORE_LABEL)

        combined_query = (
            select(
                AiSearchIndex.entity_id,
                AiSearchIndex.entity_title,
                score,
                func.first_value(AiSearchIndex.value)
                .over(partition_by=AiSearchIndex.entity_id, order_by=[similarity_expr.desc(), AiSearchIndex.path.asc()])
                .label(self.HIGHLIGHT_TEXT_LABEL),
                func.first_value(AiSearchIndex.path)
                .over(partition_by=AiSearchIndex.entity_id, order_by=[similarity_expr.desc(), AiSearchIndex.path.asc()])
                .label(self.HIGHLIGHT_PATH_LABEL),
            )
            .select_from(AiSearchIndex)
            .join(cand, cand.c.entity_id == AiSearchIndex.entity_id)
            .where(
                and_(
                    AiSearchIndex.value_type.in_(self.SEARCHABLE_FIELD_TYPES),
                    literal(self.fuzzy_term).op("<%")(AiSearchIndex.value),
                )
            )
            .distinct(AiSearchIndex.entity_id, AiSearchIndex.entity_title)
        )
        final_query = combined_query.subquery("ranked_fuzzy")

        stmt = select(
            final_query.c.entity_id,
            final_query.c.entity_title,
            final_query.c.score,
            final_query.c.highlight_text,
            final_query.c.highlight_path,
        ).select_from(final_query)

        stmt = self._apply_score_pagination(stmt, final_query.c.score, final_query.c.entity_id)

        return stmt.order_by(final_query.c.score.desc().nulls_last(), final_query.c.entity_id.asc())

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.fuzzy()

    def _apply_score_pagination(
        self, stmt: Select, score_column: ColumnElement, entity_id_column: ColumnElement
    ) -> Select:
        """Apply standard score + entity_id pagination."""
        if self.cursor is not None:
            stmt = stmt.where(
                or_(
                    score_column < self.cursor.score,
                    and_(
                        score_column == self.cursor.score,
                        entity_id_column > self.cursor.id,
                    ),
                )
            )
        return stmt
