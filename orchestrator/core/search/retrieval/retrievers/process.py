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

from sqlalchemy import Select, String, and_, cast, func, literal, select
from sqlalchemy.sql.expression import Subquery
from sqlalchemy_utils import LtreeType

from orchestrator.core.db.models import ProcessStepTable
from orchestrator.core.search.core.types import SearchMetadata
from orchestrator.core.search.retrieval.retrievers.hybrid import RrfHybridRetriever


class ProcessHybridRetriever(RrfHybridRetriever):
    """Process-specific hybrid retriever with process.last_step JSONB search.

    Extends RrfHybridRetriever so the fuzzy side also covers the ``state`` JSONB of the
    process's most recent step. For process searches:
    - Indexed fields (from AiSearchIndex): semantic + fuzzy search
    - Last step JSONB field: fuzzy search only (no embeddings for dynamic data)

    ``q_vec`` may be None, in which case only the fuzzy side runs (fuzzy-only search).
    """

    LAST_STEP_PATH = "process.last_step.state"
    LAST_STEP_CANDIDATES_LIMIT = 100

    def _fuzzy_results(self, candidate_query: Select) -> Subquery:
        """The fuzzy retriever's rows united with the last-step matches, keeping each process's best score."""
        indexed = self.fuzzy.apply(candidate_query).order_by(None)
        sources = indexed.union_all(self._last_step_results(candidate_query)).subquery("fuzzy_sources")
        return (
            select(
                sources.c.entity_id,
                sources.c.entity_title,
                sources.c.score,
                sources.c.highlight_text,
                sources.c.highlight_path,
            )
            .distinct(sources.c.entity_id)
            .order_by(sources.c.entity_id, sources.c.score.desc(), sources.c.highlight_path)
            .subquery("fuzzy_results")
        )

    def _last_step_results(self, candidate_query: Select) -> Select:
        """Candidate processes whose last step state contains the term, in the fuzzy retriever's row shape.

        Capped like the indexed candidates were before: the lateral lookup runs per candidate process,
        so the limit lets Postgres stop once enough matching steps are found.
        """
        cand = candidate_query.subquery()
        # The last step per process, through a LATERAL subquery
        last_step = (
            select(ProcessStepTable.process_id, ProcessStepTable.state)
            .where(ProcessStepTable.process_id == cand.c.entity_id)
            .order_by(ProcessStepTable.completed_at.desc())
            .limit(1)
            .lateral("last_step")
        )

        # Cast JSONB to text for substring search
        state_text = cast(last_step.c.state, String)
        score = cast(
            func.round(
                cast(func.word_similarity(self.fuzzy_term, state_text), self.SCORE_NUMERIC_TYPE), self.SCORE_PRECISION
            ),
            self.SCORE_NUMERIC_TYPE,
        )

        return (
            select(
                cand.c.entity_id,
                cand.c.entity_title,
                score.label(self.SCORE_LABEL),
                state_text.label(self.HIGHLIGHT_TEXT_LABEL),
                cast(literal(self.LAST_STEP_PATH), LtreeType).label(self.HIGHLIGHT_PATH_LABEL),
            )
            .select_from(cand)
            .join(last_step, literal(True))
            .where(and_(last_step.c.state.isnot(None), state_text.ilike(f"%{self.fuzzy_term}%")))
            .limit(self.LAST_STEP_CANDIDATES_LIMIT)
        )

    @property
    def metadata(self) -> SearchMetadata:
        return SearchMetadata.hybrid()
