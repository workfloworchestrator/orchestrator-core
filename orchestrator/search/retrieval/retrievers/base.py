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

from abc import ABC, abstractmethod
from decimal import Decimal

import structlog
from sqlalchemy import BindParameter, Numeric, Select, literal

from orchestrator.search.core.types import FieldType, SearchMetadata
from orchestrator.search.schemas.parameters import BaseSearchParameters

from ..pagination import PaginationParams

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

        Args:
            params (BaseSearchParameters): Search parameters including vector queries, fuzzy terms, and filters.
            pagination_params (PaginationParams): Pagination parameters for cursor-based paging.

        Returns:
            Retriever: A concrete retriever instance (semantic, fuzzy, hybrid, or structured).
        """

        from .fuzzy import FuzzyRetriever
        from .hybrid import RrfHybridRetriever
        from .semantic import SemanticRetriever
        from .structured import StructuredRetriever

        fuzzy_term = params.fuzzy_term
        q_vec = await cls._get_query_vector(params.vector_query, pagination_params.q_vec_override)

        # If semantic search was attempted but failed, fall back to fuzzy with the full query
        fallback_fuzzy_term = fuzzy_term
        if q_vec is None and params.vector_query is not None and params.query is not None:
            fallback_fuzzy_term = params.query

        if q_vec is not None and fallback_fuzzy_term is not None:
            return RrfHybridRetriever(q_vec, fallback_fuzzy_term, pagination_params)
        if q_vec is not None:
            return SemanticRetriever(q_vec, pagination_params)
        if fallback_fuzzy_term is not None:
            return FuzzyRetriever(fallback_fuzzy_term, pagination_params)

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
            return None

        return q_vec

    @abstractmethod
    def apply(self, candidate_query: Select) -> Select:
        """Apply the ranking logic to the given candidate query.

        Args:
            candidate_query (Select): A SQLAlchemy `Select` statement returning candidate entity IDs.

        Returns:
            Select: A new `Select` statement with ranking expressions applied.
        """
        ...

    def _quantize_score_for_pagination(self, score_value: float) -> BindParameter[Decimal]:
        """Convert score value to properly quantized Decimal parameter for pagination."""
        pas_dec = Decimal(str(score_value)).quantize(Decimal("0.000000000001"))
        return literal(pas_dec, type_=self.SCORE_NUMERIC_TYPE)

    @property
    @abstractmethod
    def metadata(self) -> SearchMetadata:
        """Return metadata describing this search strategy."""
        ...
