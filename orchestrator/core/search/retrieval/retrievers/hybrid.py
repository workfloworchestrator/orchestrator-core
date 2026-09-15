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

from collections.abc import Sequence
from typing import TypedDict

from sqlalchemy import Integer, Select, and_, case, cast, func, literal, null, or_, select
from sqlalchemy.sql.expression import CTE, ColumnElement, Label, Subquery
from sqlalchemy.types import TypeEngine

from orchestrator.core.search.core.types import EntityType, SearchMetadata
from orchestrator.core.search.retrieval.pagination import PageCursor
from orchestrator.core.search.retrieval.retrievers.base import Retriever
from orchestrator.core.search.retrieval.retrievers.fuzzy import FuzzyRetriever
from orchestrator.core.search.retrieval.retrievers.semantic import SemanticRetriever
from orchestrator.core.search.retrieval.session import SessionSetting

# Among perfect matches the text decides: the semantic term is scaled down until it cannot overturn a
# fuzzy-rank difference for this many rank levels, so it only orders entities that tie on fuzzy rank.
# Identical similarities share a dense rank, so real queries stay far below this.
PERFECT_TEXT_DECIDES_RANKS = 1000


def semantic_tiebreak_weight(k: int, ranks: int = PERFECT_TEXT_DECIDES_RANKS) -> float:
    """Largest weight for the semantic term of perfect matches that keeps `ranks` fuzzy-rank gaps decisive.

    The weighted semantic term is at most ``w / (k + 1)``; adjacent fuzzy ranks ``r`` and ``r + 1``
    differ by ``1 / ((k + r) * (k + r + 1))``, which shrinks as ``r`` grows. Equating the two at
    ``r = ranks`` gives the bound.
    """
    return (k + 1) / ((k + ranks) * (k + ranks + 1))


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
    best_fuzzy_score_col: ColumnElement,
    k: int,
    perfect_threshold: float,
    n_sources: int = 2,
    margin_factor: float = 0.05,
    score_numeric_type: TypeEngine | None = None,
    perfect_semantic_weight: float | None = None,
) -> RrfScoreSqlComponents:
    """Compute RRF (Reciprocal Rank Fusion) hybrid score as SQL expressions for database execution.

    This function implements the core scoring logic for hybrid search combining semantic
    and fuzzy ranking. It computes:
    1. Base RRF score from both ranks
    2. Perfect match detection and boosting
    3. Dynamic beta parameter based on k and n_sources
    4. Normalized final score in [0, 1] range

    Args:
        sem_rank_col: SQLAlchemy column expression for semantic rank (NULL when the entity was not
            found by the semantic retriever)
        fuzzy_rank_col: SQLAlchemy column expression for fuzzy rank (NULL when the entity was not
            found by the fuzzy retriever)
        best_fuzzy_score_col: SQLAlchemy column expression for the entity's fuzzy score, its best
            field's word similarity (NULL when the entity was not found by the fuzzy retriever)
        k: RRF constant controlling rank influence (typically 60)
        perfect_threshold: Threshold for perfect match boost (typically 0.9)
        n_sources: Number of ranking sources being fused (default: 2 for semantic + fuzzy)
        margin_factor: Margin above rrf_max as fraction (default: 0.05 = 5%)
        score_numeric_type: SQLAlchemy numeric type for casting scores
        perfect_semantic_weight: Factor applied to the semantic term of perfect matches. Among perfect
            matches the text decides: the semantic rank only breaks exact fuzzy-rank ties. Defaults to
            :func:`semantic_tiebreak_weight` for ``k``, which keeps the semantic term below the gap between
            any two adjacent fuzzy ranks up to ``PERFECT_TEXT_DECIDES_RANKS``.

    Returns:
        RrfScoreSqlComponents: Dictionary of SQL expressions for score components
            - rrf_num: Raw RRF score (cast to numeric type if provided)
            - perfect: Perfect match flag (1 if best_fuzzy_score >= threshold, else 0)
            - beta: Boost amount for perfect matches
            - rrf_max: Maximum possible RRF score
            - fused_num: RRF + perfect boost
            - normalized_score: Final score normalized to [0, 1]

    Note:
        -   Keep margin_factor small to avoid compressing perfects near 1 after normalization.

        -   The `beta` boost is calculated to be greater than the maximum possible standard
            RRF score (`rrf_max`). This guarantees that any item flagged as a "perfect" match
            will always rank above any non-perfect match.

        -   A `NULL` rank means the entity was not returned by that source and contributes
            `0` to the RRF sum; a `NULL` best fuzzy score never counts as a perfect match.
    """
    # Perfect flag to boost near perfect fuzzy matches (NULL score -> else branch -> 0)
    is_perfect = best_fuzzy_score_col >= perfect_threshold
    perfect = case((is_perfect, 1), else_=0).label("perfect_match")

    # RRF (rank-based): sum of 1/(k + rank_i) for each ranking source; a missing source contributes 0.
    # For perfect matches the semantic term is reduced to a tiebreaker (see perfect_semantic_weight).
    weight = semantic_tiebreak_weight(k) if perfect_semantic_weight is None else perfect_semantic_weight
    sem_weight = case((is_perfect, weight), else_=1.0)
    rrf_raw = func.coalesce(sem_weight * (1.0 / (k + sem_rank_col)), 0.0) + func.coalesce(
        1.0 / (k + fuzzy_rank_col), 0.0
    )
    rrf_num = cast(rrf_raw, score_numeric_type) if score_numeric_type else rrf_raw

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
    """Reciprocal Rank Fusion of the fuzzy and the semantic retriever.

    Both retrievers rank the same candidates, each yielding one row per entity with its score and the
    field to highlight. The two rankings are joined with a full outer join and fused with RRF, so an
    entity found by only one retriever still gets a score and the missing side contributes nothing.
    Entities whose fuzzy score reaches ``PERFECT_THRESHOLD`` are boosted above every non-perfect
    result. Without an embedding only the fuzzy retriever runs.
    """

    PERFECT_THRESHOLD = 0.9

    def __init__(
        self,
        q_vec: list[float] | None,
        fuzzy_term: str,
        cursor: PageCursor | None,
        k: int = 60,
        entity_type: EntityType | None = None,
        semantic_candidates_limit: int | None = None,
    ) -> None:
        self.q_vec = q_vec
        self.fuzzy_term = fuzzy_term
        self.cursor = cursor
        self.k = k
        self.entity_type = entity_type
        self.semantic_candidates_limit = semantic_candidates_limit
        # The sources paginate nothing themselves: the fused score is what pages.
        self.fuzzy = FuzzyRetriever(fuzzy_term, cursor=None)
        self.semantic = (
            SemanticRetriever(q_vec, cursor=None, entity_type=entity_type, candidates_limit=semantic_candidates_limit)
            if q_vec is not None
            else None
        )

    @property
    def session_settings(self) -> Sequence[SessionSetting]:
        return self.semantic.session_settings if self.semantic is not None else ()

    def apply(self, candidate_query: Select) -> Select:
        fuzzy_results = self._fuzzy_results(candidate_query)
        semantic_results = self._semantic_results(candidate_query)
        ranked = self._ranked_results(fuzzy_results, semantic_results)
        return self._fused(ranked, n_sources=1 if semantic_results is None else 2)

    def _fuzzy_results(self, candidate_query: Select) -> Subquery:
        """One row per entity from the fuzzy retriever: its best trigram score and the field to highlight."""
        return self.fuzzy.apply(candidate_query).order_by(None).subquery("fuzzy_results")

    def _semantic_results(self, candidate_query: Select) -> Subquery | None:
        """One row per entity from the semantic retriever, or None when there is no embedding."""
        if self.semantic is None:
            return None
        return self.semantic.apply(candidate_query).order_by(None).subquery("semantic_results")

    def _ranked_results(self, fuzzy_results: Subquery, semantic_results: Subquery | None) -> CTE:
        """Both sources joined per entity with a dense rank per source (NULL when the source missed it)."""
        f = fuzzy_results.c
        # Equal fuzzy scores are broken by the depth of the matching field: an entity whose own
        # description/title matches ranks above entities that carry the same text in a nested block.
        fuzzy_rank = func.dense_rank().over(
            order_by=[f.score.desc().nulls_last(), func.nlevel(f.highlight_path).asc().nulls_last()]
        )

        if semantic_results is None:
            # A typed NULL: an untyped NULL column in a CTE defaults to text, which breaks `k + sem_rank`.
            return (
                select(
                    f.entity_id,
                    f.entity_title,
                    f.score.label("fuzzy_score"),
                    f.highlight_text,
                    f.highlight_path,
                    cast(null(), Integer).label("sem_rank"),
                    fuzzy_rank.label("fuzzy_rank"),
                ).select_from(fuzzy_results)
            ).cte("ranked_results")

        s = semantic_results.c
        return (
            select(
                func.coalesce(f.entity_id, s.entity_id).label("entity_id"),
                func.coalesce(f.entity_title, s.entity_title).label("entity_title"),
                f.score.label("fuzzy_score"),
                func.coalesce(f.highlight_text, s.highlight_text).label(self.HIGHLIGHT_TEXT_LABEL),
                func.coalesce(f.highlight_path, s.highlight_path).label(self.HIGHLIGHT_PATH_LABEL),
                case(
                    (s.entity_id.is_(None), null()),
                    else_=func.dense_rank().over(order_by=s.score.desc().nulls_last()),
                ).label("sem_rank"),
                case((f.entity_id.is_(None), null()), else_=fuzzy_rank).label("fuzzy_rank"),
            ).select_from(fuzzy_results.outerjoin(semantic_results, f.entity_id == s.entity_id, full=True))
        ).cte("ranked_results")

    def _fused(self, ranked: CTE, n_sources: int) -> Select:
        """RRF over the per-source ranks, the perfect-match boost, keyset pagination and ordering."""
        score_components = compute_rrf_hybrid_score_sql(
            sem_rank_col=ranked.c.sem_rank,
            fuzzy_rank_col=ranked.c.fuzzy_rank,
            best_fuzzy_score_col=ranked.c.fuzzy_score,
            k=self.k,
            perfect_threshold=self.PERFECT_THRESHOLD,
            n_sources=n_sources,
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
        )

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
