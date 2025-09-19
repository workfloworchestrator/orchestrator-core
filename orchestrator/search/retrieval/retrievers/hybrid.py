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

from sqlalchemy import BindParameter, Select, and_, bindparam, case, cast, func, literal, or_, select
from sqlalchemy.sql.expression import ColumnElement

from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.types import SearchMetadata

from ..pagination import PaginationParams
from .base import Retriever


class RrfHybridRetriever(Retriever):
    """Reciprocal Rank Fusion of semantic and fuzzy ranking with parent-child retrieval."""

    def __init__(
        self,
        q_vec: list[float],
        fuzzy_term: str,
        pagination_params: PaginationParams,
        k: int = 60,
        field_candidates_limit: int = 100,
    ) -> None:
        self.q_vec = q_vec
        self.fuzzy_term = fuzzy_term
        self.page_after_score = pagination_params.page_after_score
        self.page_after_id = pagination_params.page_after_id
        self.k = k
        self.field_candidates_limit = field_candidates_limit

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()
        q_param: BindParameter[list[float]] = bindparam("q_vec", self.q_vec, type_=AiSearchIndex.embedding.type)

        best_similarity = func.word_similarity(self.fuzzy_term, AiSearchIndex.value)
        sem_expr = case(
            (AiSearchIndex.embedding.is_(None), None),
            else_=AiSearchIndex.embedding.op("<->")(q_param),
        )
        sem_val = func.coalesce(sem_expr, literal(1.0)).label("semantic_distance")

        filter_condition = literal(self.fuzzy_term).op("<%")(AiSearchIndex.value)

        field_candidates = (
            select(
                AiSearchIndex.entity_id,
                AiSearchIndex.path,
                AiSearchIndex.value,
                sem_val,
                best_similarity.label("fuzzy_score"),
            )
            .select_from(AiSearchIndex)
            .join(cand, cand.c.entity_id == AiSearchIndex.entity_id)
            .where(
                and_(
                    AiSearchIndex.value_type.in_(self.SEARCHABLE_FIELD_TYPES),
                    filter_condition,
                )
            )
            .order_by(
                best_similarity.desc().nulls_last(),
                sem_expr.asc().nulls_last(),
                AiSearchIndex.entity_id.asc(),
            )
            .limit(self.field_candidates_limit)
        ).cte("field_candidates")

        entity_scores = (
            select(
                field_candidates.c.entity_id,
                func.avg(field_candidates.c.semantic_distance).label("avg_semantic_distance"),
                func.avg(field_candidates.c.fuzzy_score).label("avg_fuzzy_score"),
            ).group_by(field_candidates.c.entity_id)
        ).cte("entity_scores")

        entity_highlights = (
            select(
                field_candidates.c.entity_id,
                func.first_value(field_candidates.c.value)
                .over(
                    partition_by=field_candidates.c.entity_id,
                    order_by=[field_candidates.c.fuzzy_score.desc(), field_candidates.c.path.asc()],
                )
                .label(self.HIGHLIGHT_TEXT_LABEL),
                func.first_value(field_candidates.c.path)
                .over(
                    partition_by=field_candidates.c.entity_id,
                    order_by=[field_candidates.c.fuzzy_score.desc(), field_candidates.c.path.asc()],
                )
                .label(self.HIGHLIGHT_PATH_LABEL),
            ).distinct(field_candidates.c.entity_id)
        ).cte("entity_highlights")

        ranked = (
            select(
                entity_scores.c.entity_id,
                entity_scores.c.avg_semantic_distance,
                entity_scores.c.avg_fuzzy_score,
                entity_highlights.c.highlight_text,
                entity_highlights.c.highlight_path,
                func.dense_rank()
                .over(
                    order_by=[entity_scores.c.avg_semantic_distance.asc().nulls_last(), entity_scores.c.entity_id.asc()]
                )
                .label("sem_rank"),
                func.dense_rank()
                .over(order_by=[entity_scores.c.avg_fuzzy_score.desc().nulls_last(), entity_scores.c.entity_id.asc()])
                .label("fuzzy_rank"),
            ).select_from(
                entity_scores.join(entity_highlights, entity_scores.c.entity_id == entity_highlights.c.entity_id)
            )
        ).cte("ranked_results")

        # RRF (rank-based)
        rrf_raw = (1.0 / (self.k + ranked.c.sem_rank)) + (1.0 / (self.k + ranked.c.fuzzy_rank))
        rrf_num = cast(rrf_raw, self.SCORE_NUMERIC_TYPE)

        # Perfect flag to boost near perfect fuzzy matches as this most likely indicates the desired record.
        perfect = case((ranked.c.avg_fuzzy_score >= 0.9, 1), else_=0).label("perfect_match")

        # Dynamic beta based on k (and number of sources)
        # rrf_max = n_sources / (k + 1)
        k_num = literal(float(self.k), type_=self.SCORE_NUMERIC_TYPE)
        n_sources = literal(2.0, type_=self.SCORE_NUMERIC_TYPE)  # semantic + fuzzy
        rrf_max = n_sources / (k_num + literal(1.0, type_=self.SCORE_NUMERIC_TYPE))

        # Choose a small positive margin above rrf_max to ensure strict separation
        # Keep it small to avoid compressing perfects near 1 after normalization
        margin = rrf_max * literal(0.05, type_=self.SCORE_NUMERIC_TYPE)  # 5% above bound
        beta = rrf_max + margin

        fused_num = rrf_num + beta * cast(perfect, self.SCORE_NUMERIC_TYPE)

        # Normalize to [0,1] via the theoretical max (beta + rrf_max)
        norm_den = beta + rrf_max
        normalized_score = fused_num / norm_den

        score = cast(
            func.round(cast(normalized_score, self.SCORE_NUMERIC_TYPE), self.SCORE_PRECISION),
            self.SCORE_NUMERIC_TYPE,
        ).label(self.SCORE_LABEL)

        stmt = select(
            ranked.c.entity_id,
            score,
            ranked.c.highlight_text,
            ranked.c.highlight_path,
            perfect.label("perfect_match"),
        ).select_from(ranked)

        stmt = self._apply_fused_pagination(stmt, score, ranked.c.entity_id)

        return stmt.order_by(
            score.desc().nulls_last(),
            ranked.c.entity_id.asc(),
        ).params(q_vec=self.q_vec)

    def _apply_fused_pagination(
        self,
        stmt: Select,
        score_column: ColumnElement,
        entity_id_column: ColumnElement,
    ) -> Select:
        """Keyset paginate by fused score + id."""
        if self.page_after_score is not None and self.page_after_id is not None:
            score_param = self._quantize_score_for_pagination(self.page_after_score)
            stmt = stmt.where(
                or_(
                    score_column < score_param,
                    and_(score_column == score_param, entity_id_column > self.page_after_id),
                )
            )
        return stmt

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.hybrid()
