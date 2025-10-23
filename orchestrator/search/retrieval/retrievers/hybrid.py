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

from typing import TypedDict

from sqlalchemy import BindParameter, Select, and_, bindparam, case, cast, func, literal, or_, select
from sqlalchemy.sql.expression import ColumnElement, Label
from sqlalchemy.types import TypeEngine

from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.types import SearchMetadata

from ..pagination import PageCursor
from .base import Retriever


class RrfScoreSqlComponents(TypedDict):
    """SQL expression components of the RRF hybrid score calculation."""

    rrf_num: ColumnElement
    perfect: Label
    beta: ColumnElement
    rrf_max: ColumnElement
    fused_num: ColumnElement
    normalized_score: ColumnElement


def compute_rrf_hybrid_score_sql(
    sem_rank_col: ColumnElement,
    fuzzy_rank_col: ColumnElement,
    avg_fuzzy_score_col: ColumnElement,
    k: int,
    perfect_threshold: float,
    n_sources: int = 2,
    margin_factor: float = 0.05,
    score_numeric_type: TypeEngine | None = None,
) -> RrfScoreSqlComponents:
    """Compute RRF (Reciprocal Rank Fusion) hybrid score as SQL expressions for database execution.

    This function implements the core scoring logic for hybrid search combining semantic
    and fuzzy ranking. It computes:
    1. Base RRF score from both ranks
    2. Perfect match detection and boosting
    3. Dynamic beta parameter based on k and n_sources
    4. Normalized final score in [0, 1] range

    Args:
        sem_rank_col: SQLAlchemy column expression for semantic rank
        fuzzy_rank_col: SQLAlchemy column expression for fuzzy rank
        avg_fuzzy_score_col: SQLAlchemy column expression for average fuzzy score
        k: RRF constant controlling rank influence (typically 60)
        perfect_threshold: Threshold for perfect match boost (typically 0.9)
        n_sources: Number of ranking sources being fused (default: 2 for semantic + fuzzy)
        margin_factor: Margin above rrf_max as fraction (default: 0.05 = 5%)
        score_numeric_type: SQLAlchemy numeric type for casting scores

    Returns:
        RrfScoreSqlComponents: Dictionary of SQL expressions for score components
            - rrf_num: Raw RRF score (cast to numeric type if provided)
            - perfect: Perfect match flag (1 if avg_fuzzy_score >= threshold, else 0)
            - beta: Boost amount for perfect matches
            - rrf_max: Maximum possible RRF score
            - fused_num: RRF + perfect boost
            - normalized_score: Final score normalized to [0, 1]

    Note:
        -   Keep margin_factor small to avoid compressing perfects near 1 after normalization.

        -   The `beta` boost is calculated to be greater than the maximum possible standard
            RRF score (`rrf_max`). This guarantees that any item flagged as a "perfect" match
            will always rank above any non-perfect match.

        -   This function assumes that rank columns do not
            contain `NULL` values. A `NULL` in any rank column will result in a `NULL` final score
            for that item.
    """
    # RRF (rank-based): sum of 1/(k + rank_i) for each ranking source
    rrf_raw = (1.0 / (k + sem_rank_col)) + (1.0 / (k + fuzzy_rank_col))
    rrf_num = cast(rrf_raw, score_numeric_type) if score_numeric_type else rrf_raw

    # Perfect flag to boost near perfect fuzzy matches
    perfect = case((avg_fuzzy_score_col >= perfect_threshold, 1), else_=0).label("perfect_match")

    # Dynamic beta based on k and number of sources
    # rrf_max = n_sources / (k + 1)
    k_num = literal(float(k), type_=score_numeric_type) if score_numeric_type else literal(float(k))
    n_sources_lit = (
        literal(float(n_sources), type_=score_numeric_type) if score_numeric_type else literal(float(n_sources))
    )
    rrf_max = n_sources_lit / (k_num + literal(1.0, type_=score_numeric_type if score_numeric_type else None))

    margin = rrf_max * literal(margin_factor, type_=score_numeric_type if score_numeric_type else None)
    beta = rrf_max + margin

    # Fused score: RRF + perfect match boost
    perfect_casted = cast(perfect, score_numeric_type) if score_numeric_type else perfect
    fused_num = rrf_num + beta * perfect_casted

    # Normalize to [0,1] via the theoretical max (beta + rrf_max)
    norm_den = beta + rrf_max
    normalized_score = fused_num / norm_den

    return RrfScoreSqlComponents(
        rrf_num=rrf_num,
        perfect=perfect,
        beta=beta,
        rrf_max=rrf_max,
        fused_num=fused_num,
        normalized_score=normalized_score,
    )


class RrfHybridRetriever(Retriever):
    """Reciprocal Rank Fusion of semantic and fuzzy ranking with parent-child retrieval."""

    def __init__(
        self,
        q_vec: list[float],
        fuzzy_term: str,
        cursor: PageCursor | None,
        k: int = 60,
        field_candidates_limit: int = 100,
    ) -> None:
        self.q_vec = q_vec
        self.fuzzy_term = fuzzy_term
        self.cursor = cursor
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
                AiSearchIndex.entity_title,
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
                field_candidates.c.entity_title,
                func.avg(field_candidates.c.semantic_distance).label("avg_semantic_distance"),
                func.avg(field_candidates.c.fuzzy_score).label("avg_fuzzy_score"),
            ).group_by(field_candidates.c.entity_id, field_candidates.c.entity_title)
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
                entity_scores.c.entity_title,
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

        # Compute RRF hybrid score
        score_components = compute_rrf_hybrid_score_sql(
            sem_rank_col=ranked.c.sem_rank,
            fuzzy_rank_col=ranked.c.fuzzy_rank,
            avg_fuzzy_score_col=ranked.c.avg_fuzzy_score,
            k=self.k,
            perfect_threshold=0.9,
            score_numeric_type=self.SCORE_NUMERIC_TYPE,
        )

        perfect = score_components["perfect"]
        normalized_score = score_components["normalized_score"]

        # Round to configured precision
        score = cast(
            func.round(cast(normalized_score, self.SCORE_NUMERIC_TYPE), self.SCORE_PRECISION),
            self.SCORE_NUMERIC_TYPE,
        ).label(self.SCORE_LABEL)

        stmt = select(
            ranked.c.entity_id,
            ranked.c.entity_title,
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
        if self.cursor is not None:
            score_param = self._quantize_score_for_pagination(self.cursor.score)
            stmt = stmt.where(
                or_(
                    score_column < score_param,
                    and_(score_column == score_param, entity_id_column > self.cursor.id),
                )
            )
        return stmt

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.hybrid()
