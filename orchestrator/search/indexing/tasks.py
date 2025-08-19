import structlog
from sqlalchemy.orm import Query

from orchestrator.db import db
from orchestrator.search.core.types import EntityType
from orchestrator.search.indexing.indexer import Indexer
from orchestrator.search.indexing.registry import ENTITY_CONFIG_REGISTRY

logger = structlog.get_logger(__name__)


def run_indexing_for_entity(
    entity_kind: EntityType,
    entity_id: str | None = None,
    dry_run: bool = False,
    force_index: bool = False,
    chunk_size: int = 1000,
) -> None:
    """Stream and index entities for the given kind.

    Builds a streaming query via the entity's registry config, disables ORM eager
    loads when applicable and delegates processing to `Indexer`.

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

    Returns:
        None
    """
    config = ENTITY_CONFIG_REGISTRY[entity_kind]

    q = config.get_all_query(entity_id)

    if isinstance(q, Query):
        q = q.enable_eagerloads(False)
        stmt = q.statement
    else:
        stmt = q

    stmt = stmt.execution_options(stream_results=True, yield_per=chunk_size)
    entities = db.session.execute(stmt).scalars()

    indexer = Indexer(config=config, dry_run=dry_run, force_index=force_index)
    indexer.run(entities, chunk_size=chunk_size)
