import hashlib
from typing import Any, Dict, Sequence, Set, Tuple, Type

import structlog
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.db import db
from orchestrator.db.database import BaseModel
from orchestrator.db.models import AiSearchIndex
from orchestrator.search.core.embedding import EmbeddingGenerator
from orchestrator.search.core.types import EntityKind, ExtractedField
from orchestrator.search.indexing.traverse import BaseTraverser

logger = structlog.get_logger(__name__)


def compute_content_hash(path: str, value: str) -> str:
    content = f"{path}:{value}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_existing_hashes(entity_id: str, index_model: Type[AiSearchIndex]) -> Dict[str, str]:
    """Retrieve existing content hashes for an entity.

    Queries the index model table for all paths and their associated content
    hashes for the given entity ID.

    Parameters
    ----------
    entity_id : str
        The unique identifier of the entity whose hashes should be retrieved.
    index_model : Type[AiSearchIndex]
        The SQLAlchemy model representing the index table to query.

    Returns:
    -------
    Dict[str, str]
        A dictionary mapping each path (as a string) to its content hash.
    """
    existing_records = (
        db.session.query(index_model.path, index_model.content_hash).filter(index_model.entity_id == entity_id).all()
    )

    return {str(record.path): record.content_hash for record in existing_records}


def identify_changes(
    fields: Sequence[ExtractedField], existing_hashes: Dict[str, str]
) -> Tuple[Set[str], Set[str], Set[str]]:
    """Identify added, updated, and deleted paths based on content hashes.

    Compares the given fields against the existing hashes in the database and
    determines which paths are new, which have updated content, and which have
    been removed.

    Parameters
    ----------
    fields : Sequence[ExtractedField]
        The current set of extracted fields for the entity.
    existing_hashes : Dict[str, str]
        A mapping of existing paths to their stored content hashes.

    Returns:
    -------
    Tuple[Set[str], Set[str], Set[str]]
        - **paths_to_add**: Paths not in `existing_hashes` that should be inserted.
        - **paths_to_update**: Paths with changed content hashes that should be updated.
        - **paths_to_delete**: Paths in `existing_hashes` but not in `fields` that should be removed.
    """
    current_paths = set()
    paths_to_add = set()
    paths_to_update = set()

    for field in fields:
        current_paths.add(field.path)
        current_hash = compute_content_hash(field.path, field.value)

        if field.path not in existing_hashes:
            paths_to_add.add(field.path)
        elif existing_hashes[field.path] != current_hash:
            paths_to_update.add(field.path)

    # Paths that exist in DB but not in current fields
    existing_paths = set(existing_hashes.keys())
    paths_to_delete = existing_paths - current_paths

    return paths_to_add, paths_to_update, paths_to_delete


def make_indexable_records(
    fields: Sequence[ExtractedField], entity_id: str, entity_kind: EntityKind, embedding_map: dict[str, list[float]]
) -> list[dict[str, Any]]:
    """Create indexable records from extracted fields and embeddings.

    Transforms the given fields and their corresponding embeddings into a list
    of dictionaries formatted for insertion into the flat index table.

    Parameters
    ----------
    fields : Sequence[ExtractedField]
        The extracted fields to index.
    entity_id : str
        The unique identifier of the entity to which the fields belong.
    entity_kind : EntityKind
        The type of entity being indexed.
    embedding_map : dict[str, list[float]]
        A mapping from the full field text (``"path: value"``) to its vector embedding.

    Returns:
    -------
    list[dict[str, Any]]
        A list of dictionaries, each representing a record ready for database insertion.
    """
    records: list[dict[str, Any]] = []
    for field in fields:
        field_text = f"{field.path}: {field.value}"
        embedding = embedding_map.get(field_text)
        content_hash = compute_content_hash(field.path, field.value)

        records.append(
            {
                "entity_id": entity_id,
                "entity_type": entity_kind.value,
                "path": Ltree(field.path),
                "value": field.value,
                "value_type": field.value_type,
                "content_hash": content_hash,
                "embedding": embedding,
            }
        )
    return records


def index_entity(
    entity: BaseModel,
    entity_kind: EntityKind,
    traverser: Type[BaseTraverser],
    index_model: Type[AiSearchIndex],
    pk_name: str,
    root_name: str,
    dry: bool,
    force_index: bool,
) -> None:
    entity_id = getattr(entity, pk_name)
    fields = traverser.get_fields(entity, pk_name=pk_name, root_name=root_name)
    if not fields:
        logger.warning("Traverser returned 0 fields", pk=getattr(entity, pk_name))
        return

    existing_hashes = {} if force_index else get_existing_hashes(str(entity_id), index_model)
    paths_to_add, paths_to_update, paths_to_delete = identify_changes(fields, existing_hashes)

    # Filter fields that need embedding generation (new or changed only)
    fields_needing_embeddings = [
        field for field in fields if field.path in paths_to_add or field.path in paths_to_update
    ]

    # Filter out semantic noise like uuids, timestamps, etc.
    fields_to_embed = [f for f in fields_needing_embeddings if f.value_type.is_embeddable()]
    texts_to_embed = [f"{f.path}: {f.value}" for f in fields_to_embed]
    embeddings = EmbeddingGenerator.generate_for_batch(texts_to_embed, dry)
    hash_exists = len(fields) - len(paths_to_add) - len(paths_to_update)

    if dry:
        indexable_data_str = "\n".join([f"{f.path}: {f.value} of type {f.value_type.value}" for f in fields])
        logger.debug(
            f"Dry Run: Would index the following {len(fields)} records for pk={entity_id}:\n{indexable_data_str}"
        )
        logger.debug(
            dry_run=dry,
            pk=str(entity_id),
            hash_exists=hash_exists,
        )
        return

    embedding_map = dict(zip(texts_to_embed, embeddings))
    records_to_insert = []

    if paths_to_delete:
        delete_paths = [Ltree(path) for path in paths_to_delete]
        delete_stmt = delete(index_model).where(index_model.entity_id == entity_id, index_model.path.in_(delete_paths))
        db.session.execute(delete_stmt)

    if fields_needing_embeddings:
        # Delete existing records that are being updated
        if paths_to_update:
            update_delete_stmt = delete(index_model).where(
                index_model.entity_id == entity_id, index_model.path.in_([Ltree(path) for path in paths_to_update])
            )
            db.session.execute(update_delete_stmt)

        # Insert new and updated records
        records_to_insert = make_indexable_records(
            fields=fields_needing_embeddings,
            entity_id=entity_id,
            entity_kind=entity_kind,
            embedding_map=embedding_map,
        )

        if records_to_insert:
            db.session.execute(insert(index_model), records_to_insert)

    logger.debug(
        "Indexed entity",
        pk=str(entity_id),
        added=len(paths_to_add),
        updated=len(paths_to_update),
        deleted=len(paths_to_delete),
        hash_exists=hash_exists,
        records_created=len(records_to_insert),
    )
