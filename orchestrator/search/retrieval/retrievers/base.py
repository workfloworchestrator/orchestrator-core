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
from orchestrator.search.query.queries import ExportQuery, SelectQuery

from ..pagination import PageCursor

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
    def route(
        cls,
        query: "SelectQuery | ExportQuery",
        cursor: PageCursor | None,
        query_embedding: list[float] | None = None,
    ) -> "Retriever":
        """Route to the appropriate retriever instance based on query plan.

        Selects the retriever type based on available search criteria:
        - Hybrid: both embedding and fuzzy term available
        - Semantic: only embedding available
        - Fuzzy: only text term available (or fallback when embedding generation fails)
        - Structured: only filters available

        Args:
            query: SelectQuery or ExportQuery with search criteria
            cursor: Pagination cursor for cursor-based paging
            query_embedding: Query embedding for semantic search, or None if not available

        Returns:
            A concrete retriever instance based on available search criteria
        """
        from .fuzzy import FuzzyRetriever
        from .hybrid import RrfHybridRetriever
        from .semantic import SemanticRetriever
        from .structured import StructuredRetriever

        fuzzy_term = query.fuzzy_term

        # If vector_query exists but embedding generation failed, fall back to fuzzy search with full query text
        if query_embedding is None and query.vector_query is not None and query.query_text is not None:
            fuzzy_term = query.query_text

        # Select retriever based on available search criteria
        if query_embedding is not None and fuzzy_term is not None:
            return RrfHybridRetriever(query_embedding, fuzzy_term, cursor)
        if query_embedding is not None:
            return SemanticRetriever(query_embedding, cursor)
        if fuzzy_term is not None:
            return FuzzyRetriever(fuzzy_term, cursor)

        return StructuredRetriever(cursor)

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

    @property
    @abstractmethod
    def metadata(self) -> SearchMetadata:
        """Return metadata describing this search strategy."""
        ...
