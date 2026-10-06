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
from sqlalchemy import CTE, Select, and_, cast, exists, func, literal, or_, select, union_all
from sqlalchemy.orm import aliased
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
    # Matches counted per term to find the rarest one; a term that reaches it is common enough not to drive.
    RARITY_SAMPLE = 2000

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
        entities = self._gated_entities(tokens, is_searchable)
        # Score every searchable field of those entities, reached through the entity_id index. The gates are
        # deliberately absent here: with them the planner can drive this scan from the trigram index again,
        # which is the whole-table visit the CTE exists to avoid.
        gated = (
            select(AiSearchIndex.entity_id, AiSearchIndex.entity_title, score.label(self.SCORE_LABEL))
            .join(entities, entities.c.entity_id == AiSearchIndex.entity_id)
            .where(is_searchable)
            .group_by(AiSearchIndex.entity_id, AiSearchIndex.entity_title)
            .having(score >= self.MIN_SCORE)
        )
        # Check candidate membership per matching row so candidate filters do not drive the initial scan.
        scored = self._restrict_to_candidates(gated, candidate_query, probe=True).subquery("ranked_fuzzy")

        # Only entities that passed the threshold get a highlight: the field with the highest average
        # similarity, preferring shorter paths on ties. The lateral lookup runs per surviving entity.
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
        """The entities in which every term gates some field, found from the rarest term outwards.

        The driving term's matches come from the trigram index; the other terms are then checked per entity
        through the entity_id index. The cost follows the rarest term instead of the most common one, which
        would otherwise mean fetching every row it matches. Which term is rarest is decided at run time by
        counting each term's matches, capped at ``RARITY_SAMPLE`` so a common term stops early: trigram
        selectivity estimates are unreliable and the planner has picked the common term on them.
        """
        gate_of = {token: literal(token).op("<%")(AiSearchIndex.value) for token in tokens}
        sampled_matches = {
            token: select(literal(1)).where(and_(is_searchable, gate)).limit(self.RARITY_SAMPLE).subquery()
            for token, gate in gate_of.items()
        }
        rarity = union_all(
            *(
                select(
                    literal(token).label("term"),
                    select(func.count()).select_from(sample).scalar_subquery().label("matches"),
                )
                for token, sample in sampled_matches.items()
            )
        ).subquery("rarity")
        driving_term = select(rarity.c.term).order_by(rarity.c.matches, rarity.c.term).limit(1).scalar_subquery()

        rows = aliased(AiSearchIndex, name="gate_rows")
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
