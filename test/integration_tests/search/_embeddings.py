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

"""Seed ai_search_index rows together with the deduplicated vector they point at."""

from uuid import UUID

from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy_utils import Ltree

from orchestrator.core.db.models import AiSearchEmbedding, AiSearchIndex
from orchestrator.core.search.core.embedding import compute_embedding_hash
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.indexing.indexer import Indexer
from orchestrator.core.settings import llm_settings


def _build_rows(
    *,
    entity_type: EntityType | str,
    entity_id: UUID | str,
    path: str,
    value: str,
    embedding: list[float] | None,
    model_id: str | None,
    title: str | None,
    value_type: FieldType,
) -> tuple[AiSearchIndex, Insert | None]:
    """Build the index row and the statement that upserts its vector, shared by the sync and async helpers."""
    entity_type_value = EntityType(entity_type).value
    embedding_hash = (
        None
        if embedding is None
        else compute_embedding_hash(model_id or llm_settings.EMBEDDING_MODEL, f"{path}: {value}")
    )
    index_row = AiSearchIndex(
        entity_type=entity_type_value,
        entity_id=entity_id,
        entity_title=title,
        path=Ltree(path),
        value=value,
        value_type=value_type,
        content_hash=Indexer._compute_content_hash(path, value, value_type, title or ""),
        embedding_hash=embedding_hash,
    )
    embedding_stmt = (
        None
        if embedding is None
        else insert(AiSearchEmbedding)
        .values(entity_type=entity_type_value, embedding_hash=embedding_hash, embedding=embedding)
        .on_conflict_do_nothing()
    )
    return index_row, embedding_stmt


def add_indexed_row(
    session: Session,
    *,
    entity_type: EntityType | str,
    entity_id: UUID | str,
    path: str,
    value: str,
    embedding: list[float] | None,
    model_id: str | None = None,
    title: str | None = None,
    value_type: FieldType = FieldType.STRING,
) -> None:
    """Add an index row to the session. A row without an embedding keeps ``embedding_hash`` NULL.

    The vector is upserted by hash, so rows with the same text share one embeddings row.
    """
    index_row, embedding_stmt = _build_rows(
        entity_type=entity_type,
        entity_id=entity_id,
        path=path,
        value=value,
        embedding=embedding,
        model_id=model_id,
        title=title,
        value_type=value_type,
    )
    session.add(index_row)
    if embedding_stmt is not None:
        session.execute(embedding_stmt)


async def add_indexed_row_async(
    session: AsyncSession,
    *,
    entity_type: EntityType | str,
    entity_id: UUID | str,
    path: str,
    value: str,
    embedding: list[float] | None,
    model_id: str | None = None,
    title: str | None = None,
    value_type: FieldType = FieldType.STRING,
) -> None:
    """Like ``add_indexed_row`` for an ``AsyncSession``."""
    index_row, embedding_stmt = _build_rows(
        entity_type=entity_type,
        entity_id=entity_id,
        path=path,
        value=value,
        embedding=embedding,
        model_id=model_id,
        title=title,
        value_type=value_type,
    )
    session.add(index_row)
    if embedding_stmt is not None:
        await session.execute(embedding_stmt)
