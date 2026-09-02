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

from typing import TypedDict

from sqlalchemy import (
    BindParameter,
    Float,
    Integer,
    Select,
    and_,
    bindparam,
    case,
    cast,
    func,
    literal,
    null,
    or_,
    select,
)
from sqlalchemy.sql.expression import CTE, ColumnElement, Label
from sqlalchemy.types import TypeEngine

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import SearchMetadata

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
    best_fuzzy_score_col: ColumnElement,
    k: int,
    perfect_threshold: float,
    n_sources: int = 2,
    margin_factor: float = 0.05,
    score_numeric_type: TypeEngine | None = None,
    perfect_semantic_weight: float = 0.002,
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
            found by the semantic source)
        fuzzy_rank_col: SQLAlchemy column expression for fuzzy rank (NULL when the entity was not
            found by the fuzzy source)
        best_fuzzy_score_col: SQLAlchemy column expression for the entity's best fuzzy field score
            (NULL when the entity was not found by the fuzzy source)
        k: RRF constant controlling rank influence (typically 60)
        perfect_threshold: Threshold for perfect match boost (typically 0.9)
        n_sources: Number of ranking sources being fused (default: 2 for semantic + fuzzy)
        margin_factor: Margin above rrf_max as fraction (default: 0.05 = 5%)
        score_numeric_type: SQLAlchemy numeric type for casting scores
        perfect_semantic_weight: Factor applied to the semantic term of perfect matches (default 0.002).
            Among perfect matches the text decides: the semantic rank only breaks exact fuzzy-rank ties.
            The default keeps the semantic term below the gap between any two adjacent fuzzy ranks up to
            rank 100 (``(k+1) / ((k+100) * (k+101))`` for k=60), so it can never overturn one.

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
    sem_weight = case((is_perfect, perfect_semantic_weight), else_=1.0)
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
    """Reciprocal Rank Fusion of two independent candidate sources.

    - The **fuzzy source** returns the index fields that trigram-match the term (``<%``) with their
      ``word_similarity``.
    - The **semantic source** returns the index fields closest to the query embedding (HNSW index).

    Each source is aggregated per entity (best field), ranked on its own, and the two rankings are
    fused with RRF. An entity found by only one source still gets a score; the missing source
    contributes nothing. Entities whose best fuzzy field reaches ``PERFECT_THRESHOLD`` are boosted
    above every non-perfect result.
    """

    PERFECT_THRESHOLD = 0.9

    def __init__(
        self,
        q_vec: list[float],
        fuzzy_term: str,
        cursor: PageCursor | None,
        k: int = 60,
        field_candidates_limit: int = 100,
        semantic_candidates_limit: int = 400,
    ) -> None:
        self.q_vec = q_vec
        self.fuzzy_term = fuzzy_term
        self.cursor = cursor
        self.k = k
        self.field_candidates_limit = field_candidates_limit
        self.semantic_candidates_limit = semantic_candidates_limit

    @property
    def session_settings(self) -> dict[str, str]:
        # With the default (non-iterative) scan pgvector returns at most ~ef_search rows from the
        # HNSW index regardless of LIMIT; the iterative scan keeps going until the LIMIT is met.
        return {"hnsw.iterative_scan": "relaxed_order"}

    def apply(self, candidate_query: Select) -> Select:
        field_candidates = self._build_fuzzy_candidates(candidate_query).cte("field_candidates")
        semantic_candidates = self._build_semantic_candidates(candidate_query).cte("semantic_candidates")
        return self._rank_and_score(field_candidates, semantic_candidates)

    # ------------------------------------------------------------------ sources

    def _build_fuzzy_candidates(self, candidate_query: Select) -> Select:
        """Index fields that trigram-match the term, best matches first, capped at `field_candidates_limit`."""
        best_similarity = func.word_similarity(self.fuzzy_term, AiSearchIndex.value)
        filter_condition = literal(self.fuzzy_term).op("<%")(AiSearchIndex.value)
        return (
            select(
                AiSearchIndex.entity_id,
                AiSearchIndex.entity_title,
                AiSearchIndex.path,
                AiSearchIndex.value,
                best_similarity.label("fuzzy_score"),
            )
            .select_from(AiSearchIndex)
            .where(
                and_(
                    AiSearchIndex.value_type.in_(self.SEARCHABLE_FIELD_TYPES),
                    filter_condition,
                    self._membership_probe(candidate_query),
                )
            )
            .order_by(best_similarity.desc().nulls_last(), AiSearchIndex.entity_id.asc(), AiSearchIndex.path.asc())
            .limit(self.field_candidates_limit)
        )

    @staticmethod
    def _membership_select(candidate_query: Select) -> Select:
        """Plain (non-DISTINCT) `entity_id` select sharing the candidate query's WHERE clause.

        Both sources restrict rows with ``entity_id IN (...)`` so the planner can drive a semi join
        from the trigram or HNSW index. That only happens when the subquery is a plain select; a
        DISTINCT/GROUP BY subquery or a JOIN against the candidate subquery makes the planner fall
        back to a hash join over a sequential scan of the whole index table.
        """
        stmt = select(AiSearchIndex.entity_id)
        if candidate_query.whereclause is not None:
            stmt = stmt.where(candidate_query.whereclause)
        return stmt

    @classmethod
    def _membership_probe(cls, candidate_query: Select) -> ColumnElement[bool]:
        """Correlated per-row candidate check for the fuzzy source.

        Trigram hits are few, so probing candidate membership row by row (an index lookup on
        ``entity_id``) beats joining the whole candidate set. A scalar subquery with LIMIT is never
        pulled up into a join by the planner, unlike ``IN``/``EXISTS``, so the trigram index stays the
        driving scan even when a structured filter's row estimate is far off.
        """
        members = cls._membership_select(candidate_query).subquery("candidate_members")
        probe = select(literal(1)).where(members.c.entity_id == AiSearchIndex.entity_id).limit(1).scalar_subquery()
        return probe.isnot(None)

    def _build_semantic_candidates(self, candidate_query: Select) -> Select:
        """Index fields closest to the query embedding, capped at `semantic_candidates_limit`."""
        q_param: BindParameter[list[float]] = bindparam("q_vec", self.q_vec, type_=AiSearchIndex.embedding.type)
        distance = AiSearchIndex.embedding.op("<->")(q_param)
        return (
            select(
                AiSearchIndex.entity_id,
                AiSearchIndex.entity_title,
                AiSearchIndex.path,
                AiSearchIndex.value,
                distance.label("semantic_distance"),
            )
            .select_from(AiSearchIndex)
            .where(
                and_(
                    AiSearchIndex.embedding.isnot(None),
                    AiSearchIndex.entity_id.in_(self._membership_select(candidate_query)),
                )
            )
            .order_by(distance.asc())
            .limit(self.semantic_candidates_limit)
        )

    # ------------------------------------------------------------ aggregation

    def _fuzzy_entity_scores(self, field_candidates: CTE) -> CTE:
        """One row per entity: best fuzzy field score and the field to highlight."""
        fc = field_candidates.c
        highlight_order = [fc.fuzzy_score.desc(), fc.path.asc()]
        return (
            select(
                fc.entity_id,
                fc.entity_title,
                func.max(fc.fuzzy_score).over(partition_by=fc.entity_id).label("best_fuzzy_score"),
                func.first_value(fc.value)
                .over(partition_by=fc.entity_id, order_by=highlight_order)
                .label(self.HIGHLIGHT_TEXT_LABEL),
                func.first_value(fc.path)
                .over(partition_by=fc.entity_id, order_by=highlight_order)
                .label(self.HIGHLIGHT_PATH_LABEL),
            ).distinct(fc.entity_id)
        ).cte("entity_scores")

    def _semantic_entity_scores(self, semantic_candidates: CTE) -> CTE:
        """One row per entity: smallest semantic distance and the field to highlight."""
        sc = semantic_candidates.c
        highlight_order = [sc.semantic_distance.asc(), sc.path.asc()]
        return (
            select(
                sc.entity_id,
                sc.entity_title,
                func.min(sc.semantic_distance).over(partition_by=sc.entity_id).label("best_semantic_distance"),
                func.first_value(sc.value)
                .over(partition_by=sc.entity_id, order_by=highlight_order)
                .label(self.HIGHLIGHT_TEXT_LABEL),
                func.first_value(sc.path)
                .over(partition_by=sc.entity_id, order_by=highlight_order)
                .label(self.HIGHLIGHT_PATH_LABEL),
            ).distinct(sc.entity_id)
        ).cte("semantic_scores")

    def _ranked_results(self, fuzzy_scores: CTE, semantic_scores: CTE | None) -> CTE:
        """Full outer join of both per-entity sources with a dense rank per source (NULL when absent)."""
        f = fuzzy_scores.c
        # Equal fuzzy scores are broken by the depth of the matching field: an entity whose own
        # description/title matches ranks above entities that carry the same text in a nested block.
        fuzzy_rank = case(
            (f.entity_id.is_(None), null()),
            else_=func.dense_rank().over(
                order_by=[f.best_fuzzy_score.desc().nulls_last(), func.nlevel(f.highlight_path).asc().nulls_last()]
            ),
        ).label("fuzzy_rank")

        if semantic_scores is None:
            # Typed NULLs: an untyped NULL column in a CTE defaults to text, which breaks `k + sem_rank`.
            return (
                select(
                    f.entity_id,
                    f.entity_title,
                    f.best_fuzzy_score,
                    cast(null(), Float).label("best_semantic_distance"),
                    f.highlight_text,
                    f.highlight_path,
                    cast(null(), Integer).label("sem_rank"),
                    fuzzy_rank,
                ).select_from(fuzzy_scores)
            ).cte("ranked_results")

        s = semantic_scores.c
        sem_rank = case(
            (s.entity_id.is_(None), null()),
            else_=func.dense_rank().over(order_by=s.best_semantic_distance.asc().nulls_last()),
        ).label("sem_rank")
        return (
            select(
                func.coalesce(f.entity_id, s.entity_id).label("entity_id"),
                func.coalesce(f.entity_title, s.entity_title).label("entity_title"),
                f.best_fuzzy_score,
                s.best_semantic_distance,
                func.coalesce(f.highlight_text, s.highlight_text).label(self.HIGHLIGHT_TEXT_LABEL),
                func.coalesce(f.highlight_path, s.highlight_path).label(self.HIGHLIGHT_PATH_LABEL),
                sem_rank,
                fuzzy_rank,
            ).select_from(fuzzy_scores.outerjoin(semantic_scores, f.entity_id == s.entity_id, full=True))
        ).cte("ranked_results")

    def _rank_and_score(self, field_candidates: CTE, semantic_candidates: CTE | None) -> Select:
        """Aggregate, rank, fuse and paginate; `semantic_candidates` is None for fuzzy-only searches."""
        fuzzy_scores = self._fuzzy_entity_scores(field_candidates)
        semantic_scores = self._semantic_entity_scores(semantic_candidates) if semantic_candidates is not None else None
        ranked = self._ranked_results(fuzzy_scores, semantic_scores)

        score_components = compute_rrf_hybrid_score_sql(
            sem_rank_col=ranked.c.sem_rank,
            fuzzy_rank_col=ranked.c.fuzzy_rank,
            best_fuzzy_score_col=ranked.c.best_fuzzy_score,
            k=self.k,
            perfect_threshold=self.PERFECT_THRESHOLD,
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

        stmt = stmt.order_by(
            score.desc().nulls_last(),
            ranked.c.entity_id.asc(),
        )
        if semantic_candidates is not None:
            stmt = stmt.params(q_vec=self.q_vec)
        return stmt

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
