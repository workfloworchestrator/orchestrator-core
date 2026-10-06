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

from functools import reduce
from operator import add
from typing import Sequence

from more_itertools import unique_everseen
from sqlalchemy import CTE, Select, and_, cast, exists, func, literal, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import ColumnElement

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import SearchMetadata
from orchestrator.core.search.retrieval.pagination import PageCursor
from orchestrator.core.search.retrieval.retrievers.base import Retriever
from orchestrator.core.search.retrieval.session import SessionSetting


def fuzzy_tokens(fuzzy_term: str) -> list[str]:
    """Split on whitespace and deduplicate terms case-insensitively.

    Ignore punctuation-only tokens. Keep the original query if no tokens remain.
    """
    tokens = [token for token in fuzzy_term.split() if any(char.isalnum() for char in token)]
    return list(unique_everseen(tokens, key=str.casefold)) or [fuzzy_term]


class FuzzyRetriever(Retriever):
    """Rank entities by averaging each query term's best field similarity.

    Each term must pass ``GATE_THRESHOLD`` in at least one searchable field.
    Terms may match different fields; their average must reach ``MIN_SCORE``.
    """

    MIN_SCORE = 0.6
    # Allow typos such as "LIIR" matching "LIR" (similarity 0.5).
    GATE_THRESHOLD = SessionSetting("pg_trgm.word_similarity_threshold", "0.4")

    def __init__(self, fuzzy_term: str, cursor: PageCursor | None) -> None:
        self.fuzzy_term = fuzzy_term
        self.cursor = cursor

    @property
    def session_settings(self) -> Sequence[SessionSetting]:
        return (self.GATE_THRESHOLD,)

    def apply(self, candidate_query: Select) -> Select:
        tokens = fuzzy_tokens(self.fuzzy_term)
        token_similarities = [func.word_similarity(token, AiSearchIndex.value) for token in tokens]

        # Terms may match different fields, so take each term's maximum before averaging.
        raw_score = reduce(add, (func.max(similarity) for similarity in token_similarities)) / len(tokens)
        score = cast(
            func.round(cast(raw_score, self.SCORE_NUMERIC_TYPE), self.SCORE_PRECISION), self.SCORE_NUMERIC_TYPE
        )

        is_searchable = AiSearchIndex.value_type.in_(self.SEARCHABLE_FIELD_TYPES)
        entities = self._gated_entities(tokens, is_searchable)
        # Keep trigram filters in the CTE so scoring can use entity_id lookups.
        gated = (
            select(AiSearchIndex.entity_id, AiSearchIndex.entity_title, score.label(self.SCORE_LABEL))
            .join(entities, entities.c.entity_id == AiSearchIndex.entity_id)
            .where(is_searchable)
            .group_by(AiSearchIndex.entity_id, AiSearchIndex.entity_title)
            .having(score >= self.MIN_SCORE)
        )
        # Check filters per matching row to avoid scanning a broad candidate set.
        scored = self._restrict_to_candidates(gated, candidate_query, probe=True).subquery("ranked_fuzzy")

        # Fetch highlights after score filtering; prefer shallower paths when field scores tie.
        field_similarity = reduce(add, token_similarities) / len(tokens)
        highlight = (
            select(
                AiSearchIndex.value.label(self.HIGHLIGHT_TEXT_LABEL),
                AiSearchIndex.path.label(self.HIGHLIGHT_PATH_LABEL),
            )
            .where(and_(AiSearchIndex.entity_id == scored.c.entity_id, is_searchable))
            .order_by(field_similarity.desc(), func.nlevel(AiSearchIndex.path).asc(), AiSearchIndex.path.asc())
            .limit(1)
            .lateral("fuzzy_highlight")
        )

        stmt = select(
            scored.c.entity_id,
            scored.c.entity_title,
            scored.c.score,
            highlight.c.highlight_text,
            highlight.c.highlight_path,
        ).select_from(scored.join(highlight, literal(True)))

        stmt = self._apply_score_pagination(stmt, scored.c.score, scored.c.entity_id)

        return stmt.order_by(scored.c.score.desc().nulls_last(), scored.c.entity_id.asc())

    def _gated_entities(self, tokens: list[str], is_searchable: ColumnElement[bool]) -> CTE:
        """Find entities where every term matches at least one searchable field.

        Start with the first term, then check every term per entity.
        Materialize the IDs to keep selection separate from scoring.
        """
        if len(tokens) == 1:
            return (
                select(AiSearchIndex.entity_id)
                .where(and_(is_searchable, literal(tokens[0]).op("<%")(AiSearchIndex.value)))
                .distinct()
                .cte("fuzzy_entities")
                .prefix_with("MATERIALIZED")
            )

        # Start with the first term instead of estimating the rarest term.
        driving_term = literal(tokens[0])

        rows = aliased(AiSearchIndex, name="gate_rows")
        # Require every term to match within the entity; different terms may match different fields.
        gated_elsewhere = [
            exists().where(
                and_(
                    rows.entity_id == AiSearchIndex.entity_id,
                    rows.value_type.in_(self.SEARCHABLE_FIELD_TYPES),
                    literal(token).op("<%")(rows.value),
                )
            )
            for token in tokens
        ]
        return (
            select(AiSearchIndex.entity_id)
            .where(and_(is_searchable, driving_term.op("<%")(AiSearchIndex.value), *gated_elsewhere))
            .distinct()
            .cte("fuzzy_entities")
            .prefix_with("MATERIALIZED")
        )

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.fuzzy()

    def _apply_score_pagination(
        self, stmt: Select, score_column: ColumnElement, entity_id_column: ColumnElement
    ) -> Select:
        """Apply standard score + entity_id pagination."""
        if self.cursor is not None:
            stmt = stmt.where(
                or_(
                    score_column < self.cursor.score,
                    and_(
                        score_column == self.cursor.score,
                        entity_id_column > self.cursor.id,
                    ),
                )
            )
        return stmt
