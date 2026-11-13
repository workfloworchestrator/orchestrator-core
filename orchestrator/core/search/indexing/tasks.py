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
from uuid import UUID

import structlog
from more_itertools import peekable
from sqlalchemy import delete, func, select, text

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.domain.context_cache import cache_subscription_models
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.core.validators import is_uuid
from orchestrator.core.search.indexing.indexer import Indexer
from orchestrator.core.search.indexing.registry import ENTITY_CONFIG_REGISTRY

logger = structlog.get_logger(__name__)


def _get_entity_count(stmt: Any) -> int | None:
    """Get total count of entities from a select statement."""

    count_stmt = select(func.count()).select_from(stmt.subquery())
    return db.session.execute(count_stmt).scalar()


def run_indexing_for_entity(
    entity_kind: EntityType,
    entity_id: str | None = None,
    dry_run: bool = False,
    force_index: bool = False,
    chunk_size: int = 1000,
    show_progress: bool = False,
) -> None:
    """Stream and index entities for the given kind.

    Builds a streaming query via the entity's registry config, disables ORM eager
    loads when applicable and delegates processing to `Indexer`.

    When `entity_id` is given and that entity no longer exists, its index records are
    removed instead, so indexing a deleted entity brings the index in line with it.

    Args:
        entity_kind (EntityType): The entity type to index (must exist in
            `ENTITY_CONFIG_REGISTRY`).
        entity_id (Optional[str]): If provided, restricts indexing to a single
            entity (UUID string).
        dry_run (bool): When True, runs the full pipeline without performing
            writes or external embedding calls.
        force_index (bool): When True, re-indexes all fields regardless of
            existing hashes.
        chunk_size (int): Number of rows fetched per round-trip and passed to
            the indexer per batch.
        show_progress (bool): When True, logs progress for each processed entity.

    Returns:
        None
    """
    config = ENTITY_CONFIG_REGISTRY[entity_kind]

    stmt = config.get_all_query(entity_id)

    total_count = _get_entity_count(stmt) if show_progress else None

    stmt = stmt.execution_options(stream_results=True, yield_per=chunk_size)
    entities = peekable(db.session.execute(stmt).scalars())

    if entity_id and not entities:
        _remove_entity_from_index(entity_kind, entity_id, dry_run)
        return

    indexer = Indexer(
        config=config,
        dry_run=dry_run,
        force_index=force_index,
        chunk_size=chunk_size,
        show_progress=show_progress,
        total_count=total_count,
    )

    with cache_subscription_models():
        indexer.run(entities)


def _remove_entity_from_index(entity_kind: EntityType, entity_id: str, dry_run: bool) -> None:
    """Delete every index record of one entity that no longer exists.

    The `Indexer` can't do this: it only cleans up the entities it is handed.

    Args:
        entity_kind (EntityType): The entity type the id belongs to.
        entity_id (str): The entity to remove. An id that is not a UUID can't be in the index and is ignored.
        dry_run (bool): When True, nothing is deleted.
    """
    if dry_run or not is_uuid(entity_id):
        return

    db.session.execute(
        delete(AiSearchIndex)
        .where(AiSearchIndex.entity_type == entity_kind.value)
        .where(AiSearchIndex.entity_id == UUID(entity_id))
        .execution_options(synchronize_session=False)
    )
    db.session.commit()
    logger.debug("Removed deleted entity from the search index", entity_kind=entity_kind.value, entity_id=entity_id)


def run_indexing_for_all_entities(force_index: bool = False) -> None:
    """Index every registered entity type, then resynchronize the distinct-paths table.

    Unchanged fields are skipped via the hash cache, so this is cheap to run after every
    migration unless `force_index` is set.
    """
    for entity_kind in ENTITY_CONFIG_REGISTRY:
        logger.info("Indexing entities", entity_kind=entity_kind.value)
        run_indexing_for_entity(entity_kind=entity_kind, force_index=force_index)
    rebuild_search_paths()


def rebuild_search_paths() -> None:
    """Recompute the ai_search_paths distinct-paths table from ai_search_index.

    Truncates the derived table and repopulates it with exact reference counts in a
    single pass. Serves as the migration backfill logic and as a drift-recovery
    command if a refcount is ever corrupted (e.g. by manual DB surgery).
    """
    db.session.execute(text("TRUNCATE TABLE ai_search_paths"))
    db.session.execute(
        text(
            "INSERT INTO ai_search_paths (entity_type, path, value_type, refcount) "
            "SELECT entity_type, path, value_type, count(*) "
            "FROM ai_search_index GROUP BY entity_type, path, value_type"
        )
    )
    db.session.commit()
