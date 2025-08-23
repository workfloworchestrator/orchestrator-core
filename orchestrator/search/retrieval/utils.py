import json

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
    if not text or not term:
        return []
    indices = []
    start = text.lower().find(term.lower())
    if start != -1:
        end = start + len(term)
        indices.append((start, end))
    return indices


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
    """Finds the original DB record for each search result and logs its traversed fields."""
    if not results:
        logger.info("No results found.")
        return

    logger.info("--- Search Results ---")
    for result in results:
        entity_id = result.entity_id
        score = result.score

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
