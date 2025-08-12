from abc import ABC, abstractmethod
from sqlalchemy import bindparam
from sqlalchemy import Select, func, literal, select, case
import structlog
from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.embedding import EmbeddingGenerator
from orchestrator.search.schemas.parameters import BaseSearchParameters

logger = structlog.get_logger(__name__)


class Ranker(ABC):
    """Abstract base class for applying a ranking strategy to a search query."""

    INDEX_MODEL = AiSearchIndex

    @classmethod
    def from_params(cls, params: BaseSearchParameters, use_rrf: bool = True) -> "Ranker":
        vq, fq = params.vector_query, params.fuzzy_term
        q_vec = None
        if vq:
            q_vec = EmbeddingGenerator.generate_for_text(vq)
            if not q_vec:
                logger.warning("Embedding generation failed; using non-semantic ranker")
                vq = None

        if vq and fq:
            return RrfHybridRanker(q_vec, fq) if use_rrf else HybridRanker(q_vec, fq)
        if vq:
            return SemanticRanker(q_vec)
        if fq:
            return FuzzyRanker(fq)
        return StructuredRanker()

    @abstractmethod
    def apply(self, candidate_query: Select) -> Select: ...


class StructuredRanker(Ranker):
    """Applies a dummy score for purely structured searches with no text query."""

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()
        return select(cand.c.entity_id, literal(1.0).label("score")).select_from(cand).order_by(cand.c.entity_id.asc())


class FuzzyRanker(Ranker):
    """Ranks results based on the max of fuzzy text similarity scores."""

    def __init__(self, fuzzy_term: str):
        self.fuzzy_term = fuzzy_term

    def apply(self, candidate_query: Select) -> Select:

        cand = candidate_query.subquery()
        score_expr = func.max(func.similarity(self.INDEX_MODEL.value, self.fuzzy_term))

        return (
            select(self.INDEX_MODEL.entity_id, score_expr)
            .select_from(self.INDEX_MODEL)
            .join(cand, cand.c.entity_id == self.INDEX_MODEL.entity_id)
            .group_by(self.INDEX_MODEL.entity_id)
            .order_by(score_expr.desc().nulls_last(), self.INDEX_MODEL.entity_id.asc())
        )


class SemanticRanker(Ranker):
    """Ranks results based on the minimum semantic vector distance."""

    def __init__(self, vector_query):
        self.vector_query = vector_query

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()

        dist = self.INDEX_MODEL.embedding.l2_distance(self.vector_query)
        score_expr = func.min(dist).label("score")

        return (
            select(self.INDEX_MODEL.entity_id, score_expr)
            .select_from(self.INDEX_MODEL)
            .join(cand, cand.c.entity_id == self.INDEX_MODEL.entity_id)
            .where(self.INDEX_MODEL.embedding.isnot(None))
            .group_by(self.INDEX_MODEL.entity_id)
            .order_by(score_expr.asc().nulls_last(), self.INDEX_MODEL.entity_id.asc())
        )


class HybridRanker(Ranker):
    """
    Ranks results by combining semantic distance and fuzzy similarity.
    Prioritizes fuzzy score, using semantic score as a tie-breaker.
    """

    def __init__(self, q_vec, fuzzy_term: str):
        self.q_vec = q_vec
        self.fuzzy_term = fuzzy_term

    def apply(self, candidate_query: Select) -> Select:
        I = self.INDEX_MODEL
        cand = candidate_query.subquery()

        dist = I.embedding.l2_distance(self.q_vec)
        # Semantic: only consider rows where an embedding exists
        sem_agg = func.min(dist).filter(I.embedding.isnot(None))
        # Fuzzy: consider all rows (strings, uuids, etc.)
        fuzzy_agg = func.max(func.similarity(I.value, self.fuzzy_term))

        score = sem_agg.label("score")

        return (
            select(I.entity_id, score)
            .select_from(I)
            .join(cand, cand.c.entity_id == I.entity_id)
            .group_by(I.entity_id)
            .order_by(
                fuzzy_agg.desc().nulls_last(),
                sem_agg.asc().nulls_last(),
                I.entity_id.asc(),
            )
        )


class RrfHybridRanker(Ranker):
    """
    RRF of semantic (distance to centroid over rows with embeddings)
    + fuzzy (max of word_similarity/similarity over ALL rows).
    """

    def __init__(self, q_vec, fuzzy_term: str, k: int = 60):
        self.q_vec = q_vec
        self.fuzzy_term = fuzzy_term
        self.k = k

    def apply(self, candidate_query: Select) -> Select:
        I = self.INDEX_MODEL
        cand = candidate_query.subquery()

        # centroid over rows that have embeddings
        q_param = bindparam("q_vec", self.q_vec, type_=I.embedding.type)
        avg_vec = func.avg(I.embedding).filter(I.embedding.isnot(None))
        sem_dist = avg_vec.op("<->")(q_param)

        # fuzzy over ALL rows, substring-friendly for partial UUIDs
        sim_base = func.similarity(I.value, self.fuzzy_term)
        sim_word = func.word_similarity(self.fuzzy_term, I.value)
        fuzzy_agg = func.max(func.greatest(sim_base, sim_word))

        scores = (
            select(
                I.entity_id,
                sem_dist.label("semantic_distance"),
                fuzzy_agg.label("fuzzy_score"),
            )
            .select_from(I)
            .join(cand, cand.c.entity_id == I.entity_id)
            .group_by(I.entity_id)
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
