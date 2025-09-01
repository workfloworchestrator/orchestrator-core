from abc import ABC, abstractmethod
from decimal import Decimal

import structlog
from sqlalchemy import BindParameter, Float, Numeric, Select, and_, bindparam, case, cast, func, literal, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import ColumnElement

from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.types import FieldType, SearchMetadata
from orchestrator.search.schemas.parameters import BaseSearchParameters

from .pagination import PaginationParams

logger = structlog.get_logger(__name__)


class Retriever(ABC):
    """Abstract base class for applying a ranking strategy to a search query."""

    SCORE_PRECISION = 12
    SCORE_NUMERIC_TYPE = Numeric(38, 12)
    HIGHLIGHT_TEXT_LABEL = "highlight_text"
    HIGHLIGHT_PATH_LABEL = "highlight_path"
    SCORE_LABEL = "score"
    SEARCHABLE_FIELD_TYPES = [
        FieldType.STRING.value,
        FieldType.UUID.value,
        FieldType.BLOCK.value,
        FieldType.RESOURCE_TYPE.value,
    ]

    @classmethod
    async def from_params(
        cls,
        params: BaseSearchParameters,
        pagination_params: PaginationParams,
    ) -> "Retriever":
        """Create the appropriate retriever instance from search parameters.

        Parameters
        ----------
        params : BaseSearchParameters
            Search parameters including vector queries, fuzzy terms, and filters.
        pagination_params : PaginationParams
            Pagination parameters for cursor-based paging.

        Returns:
        -------
        Retriever
            A concrete retriever instance (semantic, fuzzy, hybrid, or structured).
        """
        fuzzy_term = params.fuzzy_term
        q_vec = await cls._get_query_vector(params.vector_query, pagination_params.q_vec_override)

        if q_vec is not None and fuzzy_term is not None:
            return RrfHybridRetriever(q_vec, fuzzy_term, pagination_params)
        if q_vec is not None:
            return SemanticRetriever(q_vec, pagination_params)
        if fuzzy_term is not None:
            return FuzzyRetriever(fuzzy_term, pagination_params)

        return StructuredRetriever(pagination_params)

    @classmethod
    async def _get_query_vector(
        cls, vector_query: str | None, q_vec_override: list[float] | None
    ) -> list[float] | None:
        """Get query vector either from override or by generating from text."""
        if q_vec_override:
            return q_vec_override

        if not vector_query:
            return None

        from orchestrator.search.core.embedding import QueryEmbedder

        q_vec = await QueryEmbedder.generate_for_text_async(vector_query)
        if not q_vec:
            logger.warning("Embedding generation failed; using non-semantic retriever")

        return q_vec

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

    @property
    @abstractmethod
    def metadata(self) -> SearchMetadata:
        """Return metadata describing this search strategy."""
        ...


class StructuredRetriever(Retriever):
    """Applies a dummy score for purely structured searches with no text query."""

    def __init__(self, pagination_params: PaginationParams) -> None:
        self.page_after_id = pagination_params.page_after_id

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()
        stmt = select(cand.c.entity_id, literal(1.0).label("score")).select_from(cand)

        if self.page_after_id:
            stmt = stmt.where(cand.c.entity_id > self.page_after_id)

        return stmt.order_by(cand.c.entity_id.asc())

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.structured()


class FuzzyRetriever(Retriever):
    """Ranks results based on the max of fuzzy text similarity scores."""

    def __init__(self, fuzzy_term: str, pagination_params: PaginationParams) -> None:
        self.fuzzy_term = fuzzy_term
        self.page_after_score = pagination_params.page_after_score
        self.page_after_id = pagination_params.page_after_id

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
            .distinct(AiSearchIndex.entity_id)
        )
        final_query = combined_query.subquery("ranked_fuzzy")

        stmt = select(
            final_query.c.entity_id,
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
        if self.page_after_score is not None and self.page_after_id is not None:
            stmt = stmt.where(
                or_(
                    score_column < self.page_after_score,
                    and_(
                        score_column == self.page_after_score,
                        entity_id_column > self.page_after_id,
                    ),
                )
            )
        return stmt


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
        score = cast(
            func.round(cast(-raw_min, self.SCORE_NUMERIC_TYPE), self.SCORE_PRECISION), self.SCORE_NUMERIC_TYPE
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
            score_param = self._convert_to_decimal_param(self.page_after_score)
            stmt = stmt.where(
                or_(
                    score_column < score_param,
                    and_(score_column == score_param, entity_id_column > self.page_after_id),
                )
            )
        return stmt

    def _convert_to_decimal_param(self, score_value: float) -> BindParameter[Decimal]:
        """Convert score value to properly typed Decimal parameter for SQLAlchemy."""
        pas_dec = Decimal(str(score_value))
        pas_dec = pas_dec.quantize(Decimal("0.000000000001"))
        return literal(pas_dec, type_=self.SCORE_NUMERIC_TYPE)


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
        self.page_after_perfect_match = pagination_params.page_after_perfect_match
        self.page_after_score = pagination_params.page_after_score
        self.page_after_id = pagination_params.page_after_id
        self.k = k
        self.field_candidates_limit = field_candidates_limit

    def apply(self, candidate_query: Select) -> Select:
        cand = candidate_query.subquery()
        I = aliased(AiSearchIndex)
        q_param: BindParameter[list[float]] = bindparam("q_vec", self.q_vec, type_=AiSearchIndex.embedding.type)

        best_similarity = func.word_similarity(self.fuzzy_term, I.value)
        sem_expr = case(
            (I.embedding.is_(None), None),
            else_=I.embedding.op("<->")(q_param),
        )
        sem_val = func.coalesce(sem_expr, literal(1.0)).label("semantic_distance")

        filter_condition = literal(self.fuzzy_term).op("<%")(I.value)

        field_candidates = (
            select(
                I.entity_id,
                I.path,
                I.value,
                sem_val,
                best_similarity.label("fuzzy_score"),
            )
            .select_from(I)
            .join(cand, cand.c.entity_id == I.entity_id)
            .where(
                and_(
                    I.value_type.in_(self.SEARCHABLE_FIELD_TYPES),
                    filter_condition,
                )
            )
            .order_by(
                best_similarity.desc().nulls_last(),
                sem_expr.asc().nulls_last(),
                I.entity_id.asc(),
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

        rrf_raw = (1.0 / (self.k + ranked.c.sem_rank)) + (1.0 / (self.k + ranked.c.fuzzy_rank))
        score = cast(func.round(cast(rrf_raw, Numeric), self.SCORE_PRECISION), Float).label(self.SCORE_LABEL)
        perfect = case((ranked.c.avg_fuzzy_score >= 0.9, 0), else_=1).label("perfect_match")

        stmt = select(
            ranked.c.entity_id,
            score,
            ranked.c.highlight_text,
            ranked.c.highlight_path,
            perfect.label("perfect_match"),
        ).select_from(ranked)

        stmt = self._apply_hybrid_pagination(stmt, perfect, score, ranked.c.entity_id)

        return stmt.order_by(
            perfect.asc(),
            score.desc(),
            ranked.c.entity_id.asc(),
        ).params(q_vec=self.q_vec)

    def _apply_hybrid_pagination(
        self,
        stmt: Select,
        perfect_match_column: ColumnElement,
        score_column: ColumnElement,
        entity_id_column: ColumnElement,
    ) -> Select:
        """Apply 3-level cursor pagination: perfect_match + score + entity_id."""
        if (
            self.page_after_perfect_match is not None
            and self.page_after_score is not None
            and self.page_after_id is not None
        ):
            stmt = stmt.where(
                or_(
                    perfect_match_column > self.page_after_perfect_match,
                    and_(
                        perfect_match_column == self.page_after_perfect_match,
                        score_column < self.page_after_score,
                    ),
                    and_(
                        perfect_match_column == self.page_after_perfect_match,
                        score_column == self.page_after_score,
                        entity_id_column > self.page_after_id,
                    ),
                )
            )
        return stmt

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.hybrid()
