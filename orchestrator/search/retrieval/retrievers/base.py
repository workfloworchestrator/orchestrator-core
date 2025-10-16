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
from sqlalchemy import BindParameter, Numeric, Select, literal, select
from sqlalchemy_utils import Ltree

from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.types import EntityType, FieldType, SearchMetadata
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
            return RrfHybridRetriever(q_vec, fallback_fuzzy_term, pagination_params, params.entity_type)
        if q_vec is not None:
            return SemanticRetriever(q_vec, pagination_params, params.entity_type)
        if fallback_fuzzy_term is not None:
            return FuzzyRetriever(fallback_fuzzy_term, pagination_params, params.entity_type)

        return StructuredRetriever(pagination_params, params.entity_type)

    @classmethod
    async def _get_query_vector(
        cls, vector_query: str | None, q_vec_override: list[float] | None
    ) -> list[float] | None:
        """Get query vector from override (provided by engine.py)."""
        if q_vec_override:
            return q_vec_override

        if vector_query:
            logger.warning(
                "vector_query present but no q_vec_override provided - embedding should be generated in engine.py"
            )

        return None

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
        quantizer = Decimal(1).scaleb(-self.SCORE_PRECISION)
        pas_dec = Decimal(str(score_value)).quantize(quantizer)
        return literal(pas_dec, type_=self.SCORE_NUMERIC_TYPE)

    @staticmethod
    def add_title_to_query(stmt: Select, entity_type: EntityType) -> Select:
        """Add title column to a query by joining with the index table."""
        # Define title paths based on entity type
        title_path_map = {
            EntityType.SUBSCRIPTION: "subscription.description",
            EntityType.PRODUCT: "product.description",
            EntityType.WORKFLOW: "workflow.description",
            EntityType.PROCESS: "process.workflowName",
        }

        title_path = title_path_map.get(entity_type)
        if not title_path:
            # If no title path defined, return original statement
            return stmt

        # Create subquery from the original statement
        ranked = stmt.subquery("ranked")

        # Subquery to get title value for each entity
        # Use a distinct label to avoid any column name conflicts
        title_subquery = (
            select(
                AiSearchIndex.entity_id.label("title_entity_id"),
                AiSearchIndex.value.label("entity_title"),
            )
            .where(
                AiSearchIndex.entity_type == entity_type.value,
                AiSearchIndex.path == Ltree(title_path),
            )
            .subquery("titles")
        )

        # Build explicit column list to preserve order
        columns = [ranked.c.entity_id, title_subquery.c.entity_title]

        # Add remaining columns in their original order
        for col in ranked.c:
            if col.name != "entity_id":
                columns.append(col)

        return (
            select(*columns)
            .select_from(ranked)
            .outerjoin(title_subquery, ranked.c.entity_id == title_subquery.c.title_entity_id)
        )

    @property
    @abstractmethod
    def metadata(self) -> SearchMetadata:
        """Return metadata describing this search strategy."""
        ...
