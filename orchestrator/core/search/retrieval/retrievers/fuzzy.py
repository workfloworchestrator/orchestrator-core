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

from more_itertools import unique_everseen
from sqlalchemy import Select, and_, cast, func, literal, or_, select
from sqlalchemy.sql.expression import ColumnElement

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import SearchMetadata
from orchestrator.core.search.retrieval.pagination import PageCursor
from orchestrator.core.search.retrieval.retrievers.base import Retriever


def fuzzy_tokens(fuzzy_term: str) -> list[str]:
    """Split the query on whitespace and remove case-insensitive duplicates.

    Drop terms without letters or numbers because they have no trigrams to match.
    If none remain, return the original query as a single term.
    """
    tokens = [token for token in fuzzy_term.split() if any(char.isalnum() for char in token)]
    return list(unique_everseen(tokens, key=str.casefold)) or [fuzzy_term]


class FuzzyRetriever(Retriever):
    """Rank entities by the average of each query term's best trigram similarity.

    Terms can match different searchable fields of the same entity. Results must
    match at least one term through the trigram filter and have an average score
    of at least ``MIN_SCORE``.
    """

    MIN_SCORE = 0.6

    def __init__(self, fuzzy_term: str, cursor: PageCursor | None) -> None:
        self.fuzzy_term = fuzzy_term
        self.cursor = cursor

    def apply(self, candidate_query: Select) -> Select:
        tokens = fuzzy_tokens(self.fuzzy_term)
        token_similarities = [func.word_similarity(token, AiSearchIndex.value) for token in tokens]

        # Take each term's best score across the entity's fields, then average those scores.
        raw_score = reduce(add, (func.max(similarity) for similarity in token_similarities)) / len(tokens)
        score = cast(
            func.round(cast(raw_score, self.SCORE_NUMERIC_TYPE), self.SCORE_PRECISION), self.SCORE_NUMERIC_TYPE
        )

        # Fields matching any term; the <% operator uses the trigram index. A term's best score lives in
        # these rows whenever it gated one (<% is exactly word_similarity >= 0.6), so scoring only the gated
        # fields is a single index-driven pass. The only thing not counted is partial credit for a term in a
        # field no term gated; that trades a join-back of every field of every hit, which a common term
        # like "prefix" turns into a scan of most of the table.
        is_gated = and_(
            AiSearchIndex.value_type.in_(self.SEARCHABLE_FIELD_TYPES),
            or_(*(literal(token).op("<%")(AiSearchIndex.value) for token in tokens)),
        )
        gated = (
            select(AiSearchIndex.entity_id, AiSearchIndex.entity_title, score.label(self.SCORE_LABEL))
            .where(is_gated)
            .group_by(AiSearchIndex.entity_id, AiSearchIndex.entity_title)
            # The threshold is applied inside the aggregation, before anything else is computed.
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
            .where(and_(AiSearchIndex.entity_id == scored.c.entity_id, is_gated))
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
