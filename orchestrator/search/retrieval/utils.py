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

import json
import re

import structlog
from sqlalchemy import and_
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.db.database import WrappedSession
from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.types import EntityType
from orchestrator.search.indexing.registry import ENTITY_CONFIG_REGISTRY
from orchestrator.search.schemas.parameters import BaseSearchParameters
from orchestrator.search.schemas.results import SearchResult

logger = structlog.get_logger(__name__)


def generate_highlight_indices(text: str, term: str) -> list[tuple[int, int]]:
    """Finds all occurrences of individual words from the term, including both word boundary and substring matches."""
    if not text or not term:
        return []

    all_matches = []
    words = [w.strip() for w in term.split() if w.strip()]

    for word in words:
        # First find word boundary matches
        word_boundary_pattern = rf"\b{re.escape(word)}\b"
        word_matches = list(re.finditer(word_boundary_pattern, text, re.IGNORECASE))
        all_matches.extend([(m.start(), m.end()) for m in word_matches])

        # Then find all substring matches
        substring_pattern = re.escape(word)
        substring_matches = list(re.finditer(substring_pattern, text, re.IGNORECASE))
        all_matches.extend([(m.start(), m.end()) for m in substring_matches])

    return sorted(set(all_matches))


def display_filtered_paths_only(
    results: list[SearchResult], search_params: BaseSearchParameters, db_session: WrappedSession
) -> None:
    """Display only the paths that were searched for in the results."""
    if not results:
        logger.info("No results found.")
        return

    logger.info("--- Search Results ---")

    searched_paths = search_params.filters.get_all_paths() if search_params.filters else []
    if not searched_paths:
        return

    for result in results:
        for path in searched_paths:
            record: AiSearchIndex | None = (
                db_session.query(AiSearchIndex)
                .filter(and_(AiSearchIndex.entity_id == result.entity_id, AiSearchIndex.path == Ltree(path)))
                .first()
            )

            if record:
                logger.info(f"  {record.path}: {record.value}")

        logger.info("-" * 40)


def display_results(
    results: list[SearchResult],
    db_session: WrappedSession,
    score_label: str = "Score",
) -> None:
    """Display search results, showing matched field when available or uuid+name for vector search."""
    if not results:
        logger.info("No results found.")
        return

    logger.info("--- Search Results ---")
    for result in results:
        entity_id = result.entity_id
        score = result.score

        # If we have a matching field from fuzzy search, display only that
        if result.matching_field:
            logger.info(f"Entity ID: {entity_id}")
            logger.info(f"Matched field ({result.matching_field.path}): {result.matching_field.text}")
            logger.info(f"{score_label}: {score:.4f}\n" + "-" * 20)
            continue

        index_records = db_session.query(AiSearchIndex).filter(AiSearchIndex.entity_id == entity_id).all()
        if not index_records:
            logger.warning(f"Could not find indexed records for entity_id={entity_id}")
            continue

        first_record = index_records[0]
        kind = EntityType(first_record.entity_type)
        config = ENTITY_CONFIG_REGISTRY[kind]

        db_entity = db_session.get(config.table, entity_id) if config.table else None

        if db_entity and config.traverser:
            fields = config.traverser.get_fields(db_entity, config.pk_name, config.root_name)
            result_obj = {p: v for p, v, _ in fields}
            logger.info(json.dumps(result_obj, indent=2, default=str))
            logger.info(f"{score_label}: {score:.4f}\n" + "-" * 20)
        else:
            logger.warning(f"Could not display entity {kind.value} with id={entity_id}")
