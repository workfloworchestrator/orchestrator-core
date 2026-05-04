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

from abc import ABC, abstractmethod
from decimal import Decimal

import structlog
from sqlalchemy import BindParameter, Numeric, Select, literal

from orchestrator.core.search.core.types import EntityType, FieldType, RetrieverType, SearchMetadata
from orchestrator.core.search.query.queries import ExportQuery, SelectQuery

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
    def _plan(cls, query: "SelectQuery | ExportQuery") -> type["Retriever"]:
        """Pick the retriever class that will handle this query.

        Internal helper consumed by `needs_embedding()` and `route()`;
        Honors explicit `query.retriever` overrides first,
        then falls back to auto-routing based on which search criteria are
        present. Process-entity queries that would use Fuzzy or RrfHybrid are
        promoted to ProcessHybridRetriever (which adds JSONB last_step search).
        """
        from .fuzzy import FuzzyRetriever
        from .hybrid import RrfHybridRetriever
        from .process import ProcessHybridRetriever
        from .semantic import SemanticRetriever
        from .structured import StructuredRetriever

        if query.retriever == RetrieverType.FUZZY:
            retriever_cls: type[Retriever] = FuzzyRetriever
        elif query.retriever == RetrieverType.SEMANTIC:
            retriever_cls = SemanticRetriever
        elif query.retriever == RetrieverType.HYBRID:
            retriever_cls = RrfHybridRetriever
        elif query.vector_query and query.fuzzy_term:
            retriever_cls = RrfHybridRetriever
        elif query.vector_query:
            retriever_cls = SemanticRetriever
        elif query.fuzzy_term:
            retriever_cls = FuzzyRetriever
        else:
            retriever_cls = StructuredRetriever

        if query.entity_type == EntityType.PROCESS and retriever_cls in (FuzzyRetriever, RrfHybridRetriever):
            return ProcessHybridRetriever
        return retriever_cls

    @classmethod
    def needs_embedding(cls, query: "SelectQuery | ExportQuery") -> bool:
        """Whether the planned retriever for this query needs a query embedding.

        Centralizes the embedding-requirement decision so callers can ask once,
        before invoking the embedder, without needing to know which class will
        be picked.
        """
        from .hybrid import RrfHybridRetriever
        from .process import ProcessHybridRetriever
        from .semantic import SemanticRetriever

        retriever_cls = cls._plan(query)

        if retriever_cls in (SemanticRetriever, RrfHybridRetriever):
            return True
        if retriever_cls is ProcessHybridRetriever:
            # ProcessHybrid runs fuzzy-only when the caller forces FUZZY or when there's
            # no vector component to embed. A HYBRID override needs True even for UUID
            # queries so route() can raise "embedding unavailable" instead of silently
            # degrading.
            return query.retriever != RetrieverType.FUZZY and (
                query.retriever == RetrieverType.HYBRID or query.vector_query is not None
            )
        return False

    @classmethod
    def route(
        cls,
        query: "SelectQuery | ExportQuery",
        cursor: PageCursor | None,
        query_embedding: list[float] | None = None,
    ) -> "Retriever":
        """Build the concrete retriever instance for this query.

        Selects the retriever class via `_plan()`, then constructs it. The
        rules in short:

        - Hybrid:    embedding + fuzzy term available
        - Semantic:  embedding available, no fuzzy term
        - Fuzzy:    fuzzy term available (or fallback when embedding generation fails)
        - Structured: only filters available
        - Process entities use ProcessHybridRetriever in place of Fuzzy/Hybrid.

        For explicit `query.retriever` overrides, raises ValueError when
        prerequisites aren't met (missing query text, or missing embedding for
        an embedding-based retriever). For auto-routing, falls back to fuzzy
        with the full query text when embedding generation was attempted but
        failed.

        Args:
            query: SelectQuery or ExportQuery with search criteria
            cursor: Pagination cursor for cursor-based paging
            query_embedding: Query embedding for semantic search, or None if not available

        Returns:
            A concrete retriever instance.
        """
        from .fuzzy import FuzzyRetriever
        from .hybrid import RrfHybridRetriever
        from .process import ProcessHybridRetriever
        from .semantic import SemanticRetriever
        from .structured import StructuredRetriever

        is_process = query.entity_type == EntityType.PROCESS
        override = query.retriever
        retriever_cls = cls._plan(query)

        if cls.needs_embedding(query) and query_embedding is None:
            if override is not None:
                raise ValueError(
                    f"{override.value.capitalize()} retriever requested but query embedding is not available. "
                    "Embedding generation may have failed."
                )
            # Auto-routing fallback: degrade to fuzzy on full query text when the
            # embedder couldn't produce a vector. needs_embedding=True for auto-route
            # implies query.query_text is set.
            return (
                ProcessHybridRetriever(None, query.query_text, cursor)
                if is_process
                else FuzzyRetriever(query.query_text, cursor)  # type: ignore[arg-type]
            )

        # Explicit overrides honor the full query_text; auto-routed fuzzy/hybrid use
        # the (single-word) fuzzy_term from the search mixin.
        fuzzy_text = query.query_text if override is not None else query.fuzzy_term

        if retriever_cls is StructuredRetriever:
            return StructuredRetriever(cursor, query.order_by)
        if retriever_cls is FuzzyRetriever and fuzzy_text is not None:
            return FuzzyRetriever(fuzzy_text, cursor)
        if retriever_cls is SemanticRetriever and query_embedding is not None:
            return SemanticRetriever(query_embedding, cursor)
        if retriever_cls is RrfHybridRetriever and query_embedding is not None and fuzzy_text is not None:
            return RrfHybridRetriever(query_embedding, fuzzy_text, cursor)
        if retriever_cls is ProcessHybridRetriever and fuzzy_text is not None:
            return ProcessHybridRetriever(query_embedding, fuzzy_text, cursor)
        raise RuntimeError(f"Unreachable: _plan() returned {retriever_cls.__name__} but required inputs are missing")

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
