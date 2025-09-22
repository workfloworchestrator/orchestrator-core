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

from ..pagination import PaginationParams
from .base import Retriever


class SemanticRetriever(Retriever):
    """Ranks results based on the minimum semantic vector distance."""

    def __init__(self, vector_query: list[float], pagination_params: PaginationParams) -> None:
        self.vector_query = vector_query
        self.page_after_score = pagination_params.page_after_score
        self.page_after_id = pagination_params.page_after_id

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()

        dist = AiSearchIndex.embedding.l2_distance(self.vector_query)

        raw_min = func.min(dist).over(partition_by=AiSearchIndex.entity_id)

        # Normalize score to preserve ordering in accordance with other retrievers:
        # smaller distance = higher score
        similarity = literal(1.0, type_=self.SCORE_NUMERIC_TYPE) / (
            literal(1.0, type_=self.SCORE_NUMERIC_TYPE) + cast(raw_min, self.SCORE_NUMERIC_TYPE)
        )

        score = cast(
            func.round(cast(similarity, self.SCORE_NUMERIC_TYPE), self.SCORE_PRECISION), self.SCORE_NUMERIC_TYPE
        ).label(self.SCORE_LABEL)

        combined_query = (
            select(
                AiSearchIndex.entity_id,
                score,
                func.first_value(AiSearchIndex.value)
                .over(partition_by=AiSearchIndex.entity_id, order_by=[dist.asc(), AiSearchIndex.path.asc()])
                .label(self.HIGHLIGHT_TEXT_LABEL),
                func.first_value(AiSearchIndex.path)
                .over(partition_by=AiSearchIndex.entity_id, order_by=[dist.asc(), AiSearchIndex.path.asc()])
                .label(self.HIGHLIGHT_PATH_LABEL),
            )
            .select_from(AiSearchIndex)
            .join(cand, cand.c.entity_id == AiSearchIndex.entity_id)
            .where(AiSearchIndex.embedding.isnot(None))
            .distinct(AiSearchIndex.entity_id)
        )
        final_query = combined_query.subquery("ranked_semantic")

        stmt = select(
            final_query.c.entity_id,
            final_query.c.score,
            final_query.c.highlight_text,
            final_query.c.highlight_path,
        ).select_from(final_query)

        stmt = self._apply_semantic_pagination(stmt, final_query.c.score, final_query.c.entity_id)

        return stmt.order_by(final_query.c.score.desc().nulls_last(), final_query.c.entity_id.asc())

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.semantic()

    def _apply_semantic_pagination(
        self, stmt: Select, score_column: ColumnElement, entity_id_column: ColumnElement
    ) -> Select:
        """Apply semantic score pagination with precise Decimal handling."""
        if self.page_after_score is not None and self.page_after_id is not None:
            score_param = self._quantize_score_for_pagination(self.page_after_score)
            stmt = stmt.where(
                or_(
                    score_column < score_param,
                    and_(score_column == score_param, entity_id_column > self.page_after_id),
                )
            )
        return stmt
