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
from functools import reduce
from operator import add

from more_itertools import unique_everseen
from sqlalchemy import Select, and_, cast, func, intersect, literal, or_, select
from sqlalchemy.sql.expression import ColumnElement

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import SearchMetadata
from orchestrator.core.search.retrieval.pagination import PageCursor
from orchestrator.core.search.retrieval.retrievers.base import Retriever
from orchestrator.core.search.retrieval.session import SessionSetting


def fuzzy_tokens(fuzzy_term: str) -> list[str]:
    """Split the query on whitespace and remove case-insensitive duplicates.

    Drop terms without letters or numbers because they have no trigrams to match.
    If none remain, return the original query as a single term.
    """
    tokens = [token for token in fuzzy_term.split() if any(char.isalnum() for char in token)]
    return list(unique_everseen(tokens, key=str.casefold)) or [fuzzy_term]


class FuzzyRetriever(Retriever):
    """Rank entities by the average of each query term's best trigram similarity.

    Terms can match different searchable fields of the same entity. Every term must
    pass the trigram gate (``GATE_THRESHOLD``) in some field of the entity, and the
    average of the terms' best scores must reach ``MIN_SCORE``.
    """

    MIN_SCORE = 0.6
    # What `<%` requires of a single term in a single field: low enough to let a typo through ("LIIR" is 0.5
    # against "LIR"), while MIN_SCORE on the average keeps entities with only weak matches out.
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

        # Take each term's best score across the entity's fields, then average those scores.
        raw_score = reduce(add, (func.max(similarity) for similarity in token_similarities)) / len(tokens)
        score = cast(
            func.round(cast(raw_score, self.SCORE_NUMERIC_TYPE), self.SCORE_PRECISION), self.SCORE_NUMERIC_TYPE
        )

        is_searchable = AiSearchIndex.value_type.in_(self.SEARCHABLE_FIELD_TYPES)
        # A field passes a term's gate at word_similarity >= GATE_THRESHOLD; <% uses the trigram index.
        gates = [literal(token).op("<%")(AiSearchIndex.value) for token in tokens]

        # Every term has to gate some field of the entity: the entity set is the intersection of one trigram
        # index scan per term. Materialized, so the planner computes the small intersection first instead of
        # flattening it into one scan that visits every row a common term like "prefix" matches. Trigram
        # selectivity estimates are too unreliable to leave that choice to it.
        entities_per_term = [
            select(AiSearchIndex.entity_id).where(and_(is_searchable, gate)).distinct() for gate in gates
        ]
        entities = (
            (intersect(*entities_per_term) if len(entities_per_term) > 1 else entities_per_term[0])
            .cte("fuzzy_entities")
            .prefix_with("MATERIALIZED")
        )
        # Score only the gated fields of those entities: a term's best score is always among them once it
        # gated one, so nothing is lost by not scoring the entity's other fields.
        gated = (
            select(AiSearchIndex.entity_id, AiSearchIndex.entity_title, score.label(self.SCORE_LABEL))
            .join(entities, entities.c.entity_id == AiSearchIndex.entity_id)
            .where(and_(is_searchable, or_(*gates)))
            .group_by(AiSearchIndex.entity_id, AiSearchIndex.entity_title)
            .having(score >= self.MIN_SCORE)
        )
        # Check candidate membership per matching row so candidate filters do not drive the initial scan.
        scored = self._restrict_to_candidates(gated, candidate_query, probe=True).subquery("ranked_fuzzy")

        # Only entities that passed the threshold get a highlight: the gated field with the highest average
        # similarity, preferring shorter paths on ties. The lateral lookup runs per surviving entity.
        field_similarity = reduce(add, token_similarities) / len(tokens)
        highlight = (
            select(
                AiSearchIndex.value.label(self.HIGHLIGHT_TEXT_LABEL),
                AiSearchIndex.path.label(self.HIGHLIGHT_PATH_LABEL),
            )
            .where(and_(AiSearchIndex.entity_id == scored.c.entity_id, is_searchable, or_(*gates)))
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
