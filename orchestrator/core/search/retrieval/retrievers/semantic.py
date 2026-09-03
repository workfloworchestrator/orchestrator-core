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

from sqlalchemy import Select, and_, cast, func, literal, or_, select
from sqlalchemy.sql.expression import ColumnElement

from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.search.core.types import EntityType, SearchMetadata

from ..pagination import PageCursor
from .base import HNSW_ITERATIVE_SCAN, Retriever, SessionSetting


class SemanticRetriever(Retriever):
    """Ranks results based on the minimum semantic vector distance.

    Runs one of two plans. The *bounded* plan takes the `candidates_limit` fields nearest to the
    query embedding straight from the entity type's partial HNSW index and ranks only those. The
    *exhaustive* plan computes a distance for every embedded field of every candidate, which needs a
    sequential scan but can rank the whole corpus; it is used when no limit or entity type is given.
    Exports need it: one export query asks for up to `MAX_EXPORT_LIMIT` entities, and a window of
    `n` fields can yield at most `n` entities, so a window would silently truncate the export.
    """

    def __init__(
        self,
        vector_query: list[float],
        cursor: PageCursor | None,
        entity_type: EntityType | None = None,
        candidates_limit: int | None = None,
    ) -> None:
        """Initialize the retriever.

        Args:
            vector_query: Query embedding to measure distance against.
            cursor: Pagination cursor, or None for the first page.
            entity_type: Entity type to scan; required for the bounded plan, since it is rendered
                as a literal so the planner can match the per-type partial HNSW index.
            candidates_limit: How many index fields to consider. None runs the exhaustive plan.
        """
        self.vector_query = vector_query
        self.cursor = cursor
        self.entity_type = entity_type
        self.candidates_limit = candidates_limit

    @property
    def is_bounded(self) -> bool:
        """Whether this instance ranks a capped candidate window instead of the whole corpus."""
        return self.candidates_limit is not None and self.entity_type is not None

    @property
    def session_settings(self) -> Sequence[SessionSetting]:
        """Iterative scan, so the bounded plan reaches its limit instead of stopping at ~ef_search rows."""
        return (HNSW_ITERATIVE_SCAN,) if self.is_bounded else ()

    def apply(self, candidate_query: Select) -> Select:
        combined_query = (
            self._bounded_ranking(candidate_query) if self.is_bounded else self._exhaustive_ranking(candidate_query)
        )
        final_query = combined_query.subquery("ranked_semantic")

        stmt = select(
            final_query.c.entity_id,
            final_query.c.entity_title,
            final_query.c.score,
            final_query.c.highlight_text,
            final_query.c.highlight_path,
        ).select_from(final_query)

        stmt = self._apply_semantic_pagination(stmt, final_query.c.score, final_query.c.entity_id)

        return stmt.order_by(final_query.c.score.desc().nulls_last(), final_query.c.entity_id.asc())

    def _score(self, distance: ColumnElement, entity_id: ColumnElement) -> ColumnElement:
        """Turn the smallest distance per entity into a descending score in `(0, 1]`."""
        raw_min = func.min(distance).over(partition_by=entity_id)

        # Normalize score to preserve ordering in accordance with other retrievers:
        # smaller distance = higher score
        similarity = literal(1.0, type_=self.SCORE_NUMERIC_TYPE) / (
            literal(1.0, type_=self.SCORE_NUMERIC_TYPE) + cast(raw_min, self.SCORE_NUMERIC_TYPE)
        )
        return cast(
            func.round(cast(similarity, self.SCORE_NUMERIC_TYPE), self.SCORE_PRECISION), self.SCORE_NUMERIC_TYPE
        ).label(self.SCORE_LABEL)

    def _exhaustive_ranking(self, candidate_query: Select) -> Select:
        """Rank every embedded field of every candidate entity, without a candidate window."""
        cand = candidate_query.subquery()
        dist = AiSearchIndex.embedding.l2_distance(self.vector_query)

        return (
            select(
                AiSearchIndex.entity_id,
                AiSearchIndex.entity_title,
                self._score(dist, AiSearchIndex.entity_id),
                *self._highlight_columns(dist, AiSearchIndex.entity_id, AiSearchIndex.value, AiSearchIndex.path),
            )
            .select_from(AiSearchIndex)
            .join(cand, cand.c.entity_id == AiSearchIndex.entity_id)
            .where(AiSearchIndex.embedding.isnot(None))
            .distinct(AiSearchIndex.entity_id, AiSearchIndex.entity_title)
        )

    def _bounded_ranking(self, candidate_query: Select) -> Select:
        """Rank only the fields inside the nearest-neighbour window."""
        window = self._candidate_window(candidate_query).cte("semantic_candidates")
        dist = window.c.semantic_distance

        return (
            select(
                window.c.entity_id,
                window.c.entity_title,
                self._score(dist, window.c.entity_id),
                *self._highlight_columns(dist, window.c.entity_id, window.c.value, window.c.path),
            )
            .select_from(window)
            .distinct(window.c.entity_id, window.c.entity_title)
        )

    def _candidate_window(self, candidate_query: Select) -> Select:
        """Index fields closest to the query embedding, capped at `candidates_limit`.

        The candidate conditions are applied *inside* the index scan rather than through a join, so
        the iterative HNSW scan keeps walking until it has `candidates_limit` matching rows. Joining
        the candidate subquery instead would make the planner fall back to a hash join over a
        sequential scan. The entity type is rendered as a literal so the planner can prove the
        predicate of that type's partial HNSW index whatever plan cache is in use.
        """
        distance = AiSearchIndex.embedding.l2_distance(self.vector_query)
        conditions: list[ColumnElement[bool]] = [
            AiSearchIndex.embedding.isnot(None),
            AiSearchIndex.entity_type == literal(self.entity_type.value, literal_execute=True),  # type: ignore[union-attr]
        ]
        if candidate_query.whereclause is not None:
            conditions.append(candidate_query.whereclause)

        return (
            select(
                AiSearchIndex.entity_id,
                AiSearchIndex.entity_title,
                AiSearchIndex.path,
                AiSearchIndex.value,
                distance.label("semantic_distance"),
            )
            .select_from(AiSearchIndex)
            .where(and_(*conditions))
            .order_by(distance.asc())
            .limit(self.candidates_limit)
        )

    def _highlight_columns(
        self, distance: ColumnElement, entity_id: ColumnElement, value: ColumnElement, path: ColumnElement
    ) -> tuple[ColumnElement, ColumnElement]:
        """Value and path of each entity's closest field, used to highlight the match."""
        order = [distance.asc(), path.asc()]
        return (
            func.first_value(value).over(partition_by=entity_id, order_by=order).label(self.HIGHLIGHT_TEXT_LABEL),
            func.first_value(path).over(partition_by=entity_id, order_by=order).label(self.HIGHLIGHT_PATH_LABEL),
        )

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.semantic()

    def _apply_semantic_pagination(
        self, stmt: Select, score_column: ColumnElement, entity_id_column: ColumnElement
    ) -> Select:
        """Apply semantic score pagination with precise Decimal handling."""
        if self.cursor is not None:
            score_param = self._quantize_score_for_pagination(self.cursor.score)
            stmt = stmt.where(
                or_(
                    score_column < score_param,
                    and_(score_column == score_param, entity_id_column > self.cursor.id),
                )
            )
        return stmt
