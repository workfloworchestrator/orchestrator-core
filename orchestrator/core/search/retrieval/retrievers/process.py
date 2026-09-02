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

from typing import Any

from sqlalchemy import Select, String, and_, cast, func, literal, select
from sqlalchemy.sql.expression import Subquery
from sqlalchemy_utils import LtreeType

from orchestrator.core.db.models import ProcessStepTable
from orchestrator.core.search.core.types import SearchMetadata

from .hybrid import RrfHybridRetriever


class ProcessHybridRetriever(RrfHybridRetriever):
    """Process-specific hybrid retriever with process.last_step JSONB search.

    Extends RrfHybridRetriever so the fuzzy source also covers the ``state`` JSONB of the
    process's most recent step. For process searches:
    - Indexed fields (from AiSearchIndex): semantic + fuzzy search
    - Last step JSONB field: fuzzy search only (no embeddings for dynamic data)

    ``q_vec`` may be None, in which case no semantic source is built (fuzzy-only search).
    """

    q_vec: list[float] | None  # type: ignore[assignment]  # Override parent's type to allow None for fuzzy-only search

    def __init__(self, q_vec: list[float] | None, *args: Any, **kwargs: Any) -> None:
        # ProcessHybridRetriever accepts None for q_vec (fuzzy-only search)
        super().__init__(q_vec or [], *args, **kwargs)
        self.q_vec = q_vec

    @property
    def session_settings(self) -> dict[str, str]:
        return super().session_settings if self.q_vec is not None else {}

    def _build_jsonb_candidates(self, cand: Subquery) -> Select:
        """Build fuzzy candidates from the last process_step.state JSONB column."""
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

        field_candidates = (
            self._build_fuzzy_candidates(candidate_query)
            .union_all(self._build_jsonb_candidates(cand))
            .cte("field_candidates")
        )
        semantic_candidates = (
            self._build_semantic_candidates(candidate_query).cte("semantic_candidates")
            if self.q_vec is not None
            else None
        )
        return self._rank_and_score(field_candidates, semantic_candidates)

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.hybrid()
