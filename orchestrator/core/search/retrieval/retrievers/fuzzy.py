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
from sqlalchemy import CTE, Select, and_, cast, exists, func, literal, or_, select, union
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

    Candidate selection requires either every term to pass ``GATE_THRESHOLD`` somewhere in the
    entity, or the whole phrase to pass that gate and reach ``MIN_SCORE`` in one field.
    Both routes require the average of the best term similarities to reach ``MIN_SCORE`` and,
    for multi-term queries, every term to reach ``MIN_TERM_SCORE``. The whole-phrase score only
    admits candidates; the average term score determines their rank.
    """

    # Shared minimum for the final average term score and whole-phrase candidate admission.
    MIN_SCORE = 0.6
    # Allow typos such as "LIIR" matching "LIR" (similarity 0.5).
    GATE_THRESHOLD = SessionSetting("pg_trgm.word_similarity_threshold", "0.5")
    # Per-term floor for entities that pass on a whole-phrase match; see `_term_floors`.
    MIN_TERM_SCORE = 0.4

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
        term_scores = [func.max(similarity) for similarity in token_similarities]
        raw_score = reduce(add, term_scores) / len(tokens)
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
            .having(and_(score >= self.MIN_SCORE, *self._term_floors(term_scores)))
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

    def _term_floors(self, term_scores: Sequence[ColumnElement]) -> list[ColumnElement[bool]]:
        """Require every term to reach ``MIN_TERM_SCORE`` somewhere in the entity.

        This is a looser per-term minimum for entities that pass on a whole-phrase match: it forgives a
        mistyped term ("CG-3000-XS" vs "CG-2000-XL", 0.43), but not one that is essentially absent
        ("LIR" vs "ACM L2VPN ...", 0.25). Entities where every term passes ``GATE_THRESHOLD`` already
        clear it, as long as ``MIN_TERM_SCORE`` does not exceed ``GATE_THRESHOLD``.
        A single term needs no minimum: its score must reach ``MIN_SCORE`` anyway.
        """
        if len(term_scores) == 1:
            return []
        return [term_score >= self.MIN_TERM_SCORE for term_score in term_scores]

    def _gated_entities(self, tokens: list[str], is_searchable: ColumnElement[bool]) -> CTE:
        """Find entities where every term matches a searchable field, or the whole phrase matches one.

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
        every_term_matches = select(AiSearchIndex.entity_id).where(
            and_(is_searchable, driving_term.op("<%")(AiSearchIndex.value), *gated_elsewhere)
        )
        # A strong whole-phrase match may also pass, so one mistyped term among correct ones is not fatal.
        # The `<%` filter uses the trigram index; the explicit check raises the bar to MIN_SCORE.
        # Scoring then requires every term to reach MIN_TERM_SCORE (see `_term_floors`).
        phrase = literal(self.fuzzy_term)
        phrase_matches = select(AiSearchIndex.entity_id).where(
            and_(
                is_searchable,
                phrase.op("<%")(AiSearchIndex.value),
                func.word_similarity(phrase, AiSearchIndex.value) >= self.MIN_SCORE,
            )
        )
        return union(every_term_matches, phrase_matches).cte("fuzzy_entities").prefix_with("MATERIALIZED")

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
