from abc import ABC, abstractmethod
from typing import Any

import structlog
from sqlalchemy import Select, bindparam, case, func, literal, select
from sqlalchemy.sql.expression import ColumnElement

from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.embedding import QueryEmbedder
from orchestrator.search.schemas.parameters import BaseSearchParameters

logger = structlog.get_logger(__name__)
Index = AiSearchIndex


class Ranker(ABC):
    """Abstract base class for applying a ranking strategy to a search query."""

    @classmethod
    async def from_params(cls, params: BaseSearchParameters, use_rrf: bool = True) -> "Ranker":
        """Create the appropriate ranker instance from search parameters.

        Parameters
        ----------
        params : BaseSearchParameters
            Search parameters including vector queries, fuzzy terms, and filters.
        use_rrf : bool, optional
            Whether to use Reciprocal Rank Fusion for hybrid searches, by default True.

        Returns:
        -------
        Ranker
            A concrete ranker instance (semantic, fuzzy, hybrid, RRF hybrid, or structured).
        """
        vq, fq = params.vector_query, params.fuzzy_term
        q_vec = None
        if vq:
            q_vec = await QueryEmbedder.generate_for_text_async(vq)
            if not q_vec:
                logger.warning("Embedding generation failed; using non-semantic ranker")
                vq = None

        if vq and fq and q_vec is not None:
            return RrfHybridRanker(q_vec, fq) if use_rrf else HybridRanker(q_vec, fq)
        if vq and q_vec is not None:
            return SemanticRanker(q_vec)
        if fq:
            return FuzzyRanker(fq)
        return StructuredRanker()

    @abstractmethod
    def apply(self, candidate_query: Select) -> Select:
        """Apply the ranking logic to the given candidate query.

        Parameters
        ----------
        candidate_query : Select
            A SQLAlchemy `Select` statement returning candidate entity IDs.

        Returns:
        -------
        Select
            A new `Select` statement with ranking expressions applied.
        """
        ...


class StructuredRanker(Ranker):
    """Applies a dummy score for purely structured searches with no text query."""

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()
        return select(cand.c.entity_id, literal(1.0).label("score")).select_from(cand).order_by(cand.c.entity_id.asc())


class FuzzyRanker(Ranker):
    """Ranks results based on the max of fuzzy text similarity scores."""

    def __init__(self, fuzzy_term: str) -> None:
        self.fuzzy_term = fuzzy_term

    def apply(self, candidate_query: Select) -> Select:

        cand = candidate_query.subquery()
        score_expr = func.max(func.similarity(Index.value, self.fuzzy_term))

        return (
            select(Index.entity_id, score_expr.label("score"))
            .select_from(Index)
            .join(cand, cand.c.entity_id == Index.entity_id)
            .group_by(Index.entity_id)
            .order_by(score_expr.desc().nulls_last(), Index.entity_id.asc())
        )


class SemanticRanker(Ranker):
    """Ranks results based on the minimum semantic vector distance."""

    def __init__(self, vector_query: list[float]) -> None:
        self.vector_query = vector_query

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()

        dist = Index.embedding.l2_distance(self.vector_query)
        score_expr = func.min(dist).label("score")

        return (
            select(Index.entity_id, score_expr)
            .select_from(Index)
            .join(cand, cand.c.entity_id == Index.entity_id)
            .where(Index.embedding.isnot(None))
            .group_by(Index.entity_id)
            .order_by(score_expr.asc().nulls_last(), Index.entity_id.asc())
        )


class HybridRanker(Ranker):
    """Ranks results by combining semantic distance and fuzzy similarity.

    Prioritizes fuzzy score, using semantic score as a tie-breaker.
    """

    def __init__(self, q_vec: list[float], fuzzy_term: str) -> None:
        self.q_vec = q_vec
        self.fuzzy_term = fuzzy_term

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()

        dist = Index.embedding.l2_distance(self.q_vec)
        # Semantic: only consider rows where an embedding exists
        sem_agg = func.min(dist).filter(Index.embedding.isnot(None))
        # Fuzzy: consider all rows (strings, uuids, etc.)
        fuzzy_agg = func.max(func.similarity(Index.value, self.fuzzy_term))

        score = sem_agg.label("score")

        return (
            select(Index.entity_id, score)
            .select_from(Index)
            .join(cand, cand.c.entity_id == Index.entity_id)
            .group_by(Index.entity_id)
            .order_by(
                fuzzy_agg.desc().nulls_last(),
                sem_agg.asc().nulls_last(),
                Index.entity_id.asc(),
            )
        )


class RrfHybridRanker(Ranker):
    """Reciprocal Rank Fusion of semantic and fuzzy ranking."""

    def __init__(self, q_vec: list[float], fuzzy_term: str, k: int = 60) -> None:
        self.q_vec = q_vec
        self.fuzzy_term = fuzzy_term
        self.k = k

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()

        # centroid over rows that have embeddings
        q_param: ColumnElement[Any] = bindparam("q_vec", self.q_vec, type_=Index.embedding.type)
        avg_vec = func.avg(Index.embedding).filter(Index.embedding.isnot(None))
        sem_dist = avg_vec.op("<->")(q_param)

        # fuzzy over ALL rows, substring-friendly for partial UUIDs
        sim_base = func.similarity(Index.value, self.fuzzy_term)
        sim_word = func.word_similarity(self.fuzzy_term, Index.value)
        fuzzy_agg = func.max(func.greatest(sim_base, sim_word))

        scores = (
            select(
                Index.entity_id,
                sem_dist.label("semantic_distance"),
                fuzzy_agg.label("fuzzy_score"),
            )
            .select_from(Index)
            .join(cand, cand.c.entity_id == Index.entity_id)
            .group_by(Index.entity_id)
            .cte("scores")
        )

        ranked = select(
            scores.c.entity_id,
            scores.c.semantic_distance,
            scores.c.fuzzy_score,
            func.dense_rank().over(order_by=scores.c.semantic_distance.asc().nulls_last()).label("sem_rank"),
            func.dense_rank().over(order_by=scores.c.fuzzy_score.desc().nulls_last()).label("fuzzy_rank"),
        ).cte("ranked_results")

        rrf = (1.0 / (self.k + ranked.c.sem_rank)) + (1.0 / (self.k + ranked.c.fuzzy_rank))
        score_expr = rrf.label("score")
        perfect = case((ranked.c.fuzzy_score >= 0.9, 0), else_=1)

        return (
            select(ranked.c.entity_id, score_expr)
            .select_from(ranked)
            .order_by(perfect.asc(), score_expr.desc(), ranked.c.entity_id.asc())
            .params(q_vec=self.q_vec)
        )
