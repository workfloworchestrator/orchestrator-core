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
from orchestrator.core.search.retrieval.session import HNSW_ITERATIVE_SCAN, SessionSetting

from ..pagination import PageCursor
from .base import Retriever


class SemanticRetriever(Retriever):
    """Ranks results based on the minimum semantic vector distance."""

    def __init__(
        self,
        vector_query: list[float],
        cursor: PageCursor | None,
        entity_type: EntityType | None = None,
        candidates_limit: int | None = None,
    ) -> None:
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
        """Session settings needed by the bounded HNSW plan."""
        return (HNSW_ITERATIVE_SCAN,) if self.is_bounded else ()

    def apply(self, candidate_query: Select) -> Select:
        use_bounded_plan = self.is_bounded and self._supports_bounded_plan(candidate_query)

        if use_bounded_plan:
            source = self._candidate_window(candidate_query).cte("semantic_candidates")
            entity_id = source.c.entity_id
            entity_title = source.c.entity_title
            value = source.c.value
            path = source.c.path
            dist = source.c.semantic_distance
            from_clause = source
        else:
            cand = candidate_query.subquery()
            entity_id = AiSearchIndex.entity_id
            entity_title = AiSearchIndex.entity_title
            value = AiSearchIndex.value
            path = AiSearchIndex.path
            dist = AiSearchIndex.embedding.l2_distance(self.vector_query)
            from_clause = AiSearchIndex.__table__.join(cand, cand.c.entity_id == AiSearchIndex.entity_id)

        raw_min = func.min(dist).over(partition_by=entity_id)

        # Normalize score to preserve ordering in accordance with other retrievers:
        # smaller distance = higher score
        similarity = literal(1.0, type_=self.SCORE_NUMERIC_TYPE) / (
            literal(1.0, type_=self.SCORE_NUMERIC_TYPE) + cast(raw_min, self.SCORE_NUMERIC_TYPE)
        )

        score = cast(
            func.round(cast(similarity, self.SCORE_NUMERIC_TYPE), self.SCORE_PRECISION), self.SCORE_NUMERIC_TYPE
        ).label(self.SCORE_LABEL)

        combined_query = (
            select(
                entity_id,
                entity_title,
                score,
                func.first_value(value)
                .over(partition_by=entity_id, order_by=[dist.asc(), path.asc()])
                .label(self.HIGHLIGHT_TEXT_LABEL),
                func.first_value(path)
                .over(partition_by=entity_id, order_by=[dist.asc(), path.asc()])
                .label(self.HIGHLIGHT_PATH_LABEL),
            )
            .select_from(from_clause)
            .distinct(entity_id, entity_title)
        )
        if not use_bounded_plan:
            combined_query = combined_query.where(AiSearchIndex.embedding.isnot(None))
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

    @staticmethod
    def _supports_bounded_plan(candidate_query: Select) -> bool:
        """Only allow query shapes whose semantics survive copying their filters into the HNSW window."""
        columns = list(candidate_query.selected_columns)
        if (
            candidate_query.get_final_froms() != [AiSearchIndex.__table__]
            or len(columns) != 2
            or not columns[0].shares_lineage(AiSearchIndex.entity_id)
            or not columns[1].shares_lineage(AiSearchIndex.entity_title)
        ):
            return False

        expected = select(*columns).where(*candidate_query._where_criteria).distinct()

        return candidate_query.compare(expected)

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
