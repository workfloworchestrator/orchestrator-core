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
    """The whitespace-separated terms of the query that are matched independently.

    Terms are deduplicated case-insensitively (trigrams ignore case) and terms without an alphanumeric
    character are dropped, as pg_trgm extracts no trigrams from them and they would only drag the score
    down. A query without any such term is matched as a whole.
    """
    tokens = [token for token in fuzzy_term.split() if any(char.isalnum() for char in token)]
    return list(unique_everseen(tokens, key=str.casefold)) or [fuzzy_term]


class FuzzyRetriever(Retriever):
    """Ranks entities by how well each query term trigram-matches their fields.

    Every term of the query is matched on its own, so terms need not be adjacent nor in the same field:
    ``ACM LIR`` matches ``ACM prefix LIR``. A term's score is its best ``word_similarity`` over the
    entity's fields and the entity's score is the mean over the terms, so an entity that matches all
    terms ranks above one that matches some, while each term keeps its typo tolerance.

    An entity is a hit when one of its fields passes the trigram gate for any term, so the trigram index
    still drives the plan. Hits are then scored over all their searchable fields, including those that
    did not pass the gate: a term that only partially matches a field still counts towards the mean. An
    entity is kept when its score reaches ``MIN_SCORE``, the default word similarity threshold of the
    gate: a single common term such as ``with`` matching does not make an entity a fuzzy hit.
    """

    MIN_SCORE = 0.6

    def __init__(self, fuzzy_term: str, cursor: PageCursor | None) -> None:
        self.fuzzy_term = fuzzy_term
        self.cursor = cursor

    def apply(self, candidate_query: Select) -> Select:
        tokens = fuzzy_tokens(self.fuzzy_term)
        token_similarities = [func.word_similarity(token, AiSearchIndex.value) for token in tokens]

        # The highlighted field is the one matching the terms best, and among equally good ones the
        # shallowest: an entity's own description over the same text inside a nested block.
        field_similarity = reduce(add, token_similarities) / len(tokens)
        highlight_order = [field_similarity.desc(), func.nlevel(AiSearchIndex.path).asc(), AiSearchIndex.path.asc()]

        token_best = [
            func.max(similarity).over(partition_by=AiSearchIndex.entity_id) for similarity in token_similarities
        ]
        raw_score = reduce(add, token_best) / len(tokens)
        score = cast(
            func.round(cast(raw_score, self.SCORE_NUMERIC_TYPE), self.SCORE_PRECISION), self.SCORE_NUMERIC_TYPE
        ).label(self.SCORE_LABEL)

        is_searchable = AiSearchIndex.value_type.in_(self.SEARCHABLE_FIELD_TYPES)
        gated = (
            select(AiSearchIndex.entity_id)
            .where(and_(is_searchable, or_(*(literal(token).op("<%")(AiSearchIndex.value) for token in tokens))))
            .group_by(AiSearchIndex.entity_id)
        )
        # Trigram hits are few: probing candidate membership per hit keeps the trigram index driving the
        # plan even under a broad structured filter, where joining the candidate set does not.
        hits = self._restrict_to_candidates(gated, candidate_query, probe=True).subquery("fuzzy_hits")

        # Every searchable field of a hit is scored, not only the gated ones, so each term's best match
        # comes from all of the entity's fields.
        scored = (
            select(
                AiSearchIndex.entity_id,
                AiSearchIndex.entity_title,
                score,
                func.first_value(AiSearchIndex.value)
                .over(partition_by=AiSearchIndex.entity_id, order_by=highlight_order)
                .label(self.HIGHLIGHT_TEXT_LABEL),
                func.first_value(AiSearchIndex.path)
                .over(partition_by=AiSearchIndex.entity_id, order_by=highlight_order)
                .label(self.HIGHLIGHT_PATH_LABEL),
            )
            .select_from(AiSearchIndex)
            .join(hits, hits.c.entity_id == AiSearchIndex.entity_id)
            .where(is_searchable)
            .distinct(AiSearchIndex.entity_id, AiSearchIndex.entity_title)
        )
        final_query = scored.subquery("ranked_fuzzy")

        stmt = (
            select(
                final_query.c.entity_id,
                final_query.c.entity_title,
                final_query.c.score,
                final_query.c.highlight_text,
                final_query.c.highlight_path,
            )
            .select_from(final_query)
            .where(final_query.c.score >= self.MIN_SCORE)
        )

        stmt = self._apply_score_pagination(stmt, final_query.c.score, final_query.c.entity_id)

        return stmt.order_by(final_query.c.score.desc().nulls_last(), final_query.c.entity_id.asc())

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
