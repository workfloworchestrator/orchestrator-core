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

from typing import Any

from sqlalchemy import BindParameter, Select, String, and_, case, cast, func, literal, select
from sqlalchemy.sql.expression import ColumnElement, Label
from sqlalchemy_utils import LtreeType

from orchestrator.db.models import AiSearchIndex, ProcessStepTable
from orchestrator.search.core.types import SearchMetadata

from .hybrid import RrfHybridRetriever, compute_rrf_hybrid_score_sql


class ProcessHybridRetriever(RrfHybridRetriever):
    """Process-specific hybrid retriever with process.last_step JSONB search.

    Extends RrfHybridRetriever to include fuzzy search over the process.last_step
    (JSONB) column. For process searches:
    - Indexed fields (from AiSearchIndex): semantic + fuzzy search
    - Last step JSONB field: fuzzy search only (no embeddings for dynamic data)

    The retriever:
    1. Gets field candidates from AiSearchIndex
    2. Uses process.last_step JSONB column directly for fuzzy matching
    3. Combines both sources (indexed + JSONB) in unified ranking
    """

    q_vec: list[float] | None  # type: ignore[assignment]  # Override parent's type to allow None for fuzzy-only search

    def __init__(self, q_vec: list[float] | None, *args: Any, **kwargs: Any) -> None:
        # ProcessHybridRetriever accepts None for q_vec (fuzzy-only search)
        # We pass empty list to parent to satisfy type requirements, but override behavior in _get_semantic_distance_expr
        super().__init__(q_vec or [], *args, **kwargs)
        self.q_vec = q_vec

    def _get_semantic_distance_expr(self) -> Label[Any]:
        """Get semantic distance expression, handling optional q_vec."""
        if self.q_vec is None:
            return literal(1.0).label("semantic_distance")

        from sqlalchemy import bindparam

        q_param: BindParameter[list[float]] = bindparam("q_vec", type_=AiSearchIndex.embedding.type)
        sem_expr = case(
            (AiSearchIndex.embedding.is_(None), None),
            else_=AiSearchIndex.embedding.op("<->")(q_param),
        )
        return func.coalesce(sem_expr, literal(1.0)).label("semantic_distance")

    def _build_indexed_candidates(
        self, cand: Any, sem_val: Label[Any], best_similarity: ColumnElement[Any], filter_condition: ColumnElement[Any]
    ) -> Select:
        """Build candidates from indexed fields in AiSearchIndex."""
        return (
            select(
                AiSearchIndex.entity_id,
                AiSearchIndex.entity_title,
                AiSearchIndex.path,
                AiSearchIndex.value,
                sem_val,
                best_similarity.label("fuzzy_score"),
            )
            .select_from(AiSearchIndex)
            .join(cand, cand.c.entity_id == AiSearchIndex.entity_id)
            .where(
                and_(
                    AiSearchIndex.value_type.in_(self.SEARCHABLE_FIELD_TYPES),
                    filter_condition,
                )
            )
            .limit(self.field_candidates_limit)
        )

    def _build_jsonb_candidates(self, cand: Any) -> Select:
        """Build candidates from last process_step.state JSONB column."""
        # Get the last step per process using LATERAL subquery
        last_step_subq = (
            select(ProcessStepTable.process_id, ProcessStepTable.state)
            .where(ProcessStepTable.process_id == cand.c.entity_id)
            .order_by(ProcessStepTable.completed_at.desc())
            .limit(1)
            .lateral("last_step")
        )

        # Cast JSONB to text for substring search
        state_text = cast(last_step_subq.c.state, String)
        jsonb_fuzzy_score = func.word_similarity(self.fuzzy_term, state_text)
        jsonb_filter = state_text.ilike(f"%{self.fuzzy_term}%")

        return (
            select(
                cand.c.entity_id,
                cand.c.entity_title,
                cast(literal("process.last_step.state"), LtreeType).label("path"),
                state_text.label("value"),
                literal(1.0).label("semantic_distance"),
                jsonb_fuzzy_score.label("fuzzy_score"),
            )
            .select_from(cand)
            .join(last_step_subq, literal(True))
            .where(and_(last_step_subq.c.state.isnot(None), jsonb_filter))
            .limit(self.field_candidates_limit)
        )

    def apply(self, candidate_query: Select) -> Select:
        """Apply process-specific hybrid search with process.last_step JSONB.

        Args:
            candidate_query: Base query returning process entity_id candidates

        Returns:
            Select statement with RRF scoring including last step JSONB fields
        """
        cand = candidate_query.subquery()

        best_similarity = func.word_similarity(self.fuzzy_term, AiSearchIndex.value)
        sem_val = self._get_semantic_distance_expr()
        filter_condition = literal(self.fuzzy_term).op("<%")(AiSearchIndex.value)

        indexed_candidates = self._build_indexed_candidates(cand, sem_val, best_similarity, filter_condition)
        jsonb_candidates = self._build_jsonb_candidates(cand)

        field_candidates = indexed_candidates.union_all(jsonb_candidates).cte("field_candidates")

        entity_scores = (
            select(
                field_candidates.c.entity_id,
                field_candidates.c.entity_title,
                func.avg(field_candidates.c.semantic_distance).label("avg_semantic_distance"),
                func.avg(field_candidates.c.fuzzy_score).label("avg_fuzzy_score"),
            ).group_by(field_candidates.c.entity_id, field_candidates.c.entity_title)
        ).cte("entity_scores")

        entity_highlights = (
            select(
                field_candidates.c.entity_id,
                func.first_value(field_candidates.c.value)
                .over(
                    partition_by=field_candidates.c.entity_id,
                    order_by=[field_candidates.c.fuzzy_score.desc(), field_candidates.c.path.asc()],
                )
                .label(self.HIGHLIGHT_TEXT_LABEL),
                func.first_value(field_candidates.c.path)
                .over(
                    partition_by=field_candidates.c.entity_id,
                    order_by=[field_candidates.c.fuzzy_score.desc(), field_candidates.c.path.asc()],
                )
                .label(self.HIGHLIGHT_PATH_LABEL),
            ).distinct(field_candidates.c.entity_id)
        ).cte("entity_highlights")

        ranked = (
            select(
                entity_scores.c.entity_id,
                entity_scores.c.entity_title,
                entity_scores.c.avg_semantic_distance,
                entity_scores.c.avg_fuzzy_score,
                entity_highlights.c.highlight_text,
                entity_highlights.c.highlight_path,
                func.dense_rank()
                .over(
                    order_by=[entity_scores.c.avg_semantic_distance.asc().nulls_last(), entity_scores.c.entity_id.asc()]
                )
                .label("sem_rank"),
                func.dense_rank()
                .over(order_by=[entity_scores.c.avg_fuzzy_score.desc().nulls_last(), entity_scores.c.entity_id.asc()])
                .label("fuzzy_rank"),
            ).select_from(
                entity_scores.join(entity_highlights, entity_scores.c.entity_id == entity_highlights.c.entity_id)
            )
        ).cte("ranked_results")

        score_components = compute_rrf_hybrid_score_sql(
            sem_rank_col=ranked.c.sem_rank,
            fuzzy_rank_col=ranked.c.fuzzy_rank,
            avg_fuzzy_score_col=ranked.c.avg_fuzzy_score,
            k=self.k,
            perfect_threshold=0.9,
            score_numeric_type=self.SCORE_NUMERIC_TYPE,
        )

        perfect = score_components["perfect"]
        normalized_score = score_components["normalized_score"]

        score = cast(
            func.round(cast(normalized_score, self.SCORE_NUMERIC_TYPE), self.SCORE_PRECISION),
            self.SCORE_NUMERIC_TYPE,
        ).label(self.SCORE_LABEL)

        stmt = select(
            ranked.c.entity_id,
            ranked.c.entity_title,
            score,
            ranked.c.highlight_text,
            ranked.c.highlight_path,
            perfect.label("perfect_match"),
        ).select_from(ranked)

        stmt = self._apply_fused_pagination(stmt, score, ranked.c.entity_id)

        stmt = stmt.order_by(
            score.desc().nulls_last(),
            ranked.c.entity_id.asc(),
        )

        if self.q_vec is not None:
            stmt = stmt.params(q_vec=self.q_vec)

        return stmt

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.hybrid()
