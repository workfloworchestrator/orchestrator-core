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

import hashlib
from collections.abc import Generator, Iterable, Iterator
from contextlib import contextmanager, nullcontext
from functools import lru_cache
from typing import Any

import structlog
from litellm.utils import encode, get_max_tokens
from sqlalchemy import delete, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.postgresql.dml import Insert
from sqlalchemy.orm import Session
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.db import db
from orchestrator.db.models import AiSearchIndex
from orchestrator.llm_settings import llm_settings
from orchestrator.search.core.embedding import EmbeddingIndexer
from orchestrator.search.core.types import ExtractedField, IndexableRecord
from orchestrator.search.indexing.registry import EntityConfig
from orchestrator.search.indexing.traverse import DatabaseEntity

logger = structlog.get_logger(__name__)


@contextmanager
def _maybe_begin(session: Session | None) -> Iterator[None]:
    if session is None:
        yield
    else:
        with session.begin():
            yield


class Indexer:
    """Index entities into `AiSearchIndex` using streaming reads and batched writes.

    Entities are read from a streaming iterator and accumulated into chunks of
    size `chunk_size`. For each chunk, the indexer extracts fields, diffs via
    content hashes, deletes stale paths, and prepares upserts using a two-list
    buffer:
    - Embeddable list (STRING fields): maintains a running token count against a
        token budget (model context window minus a safety margin) and flushes when
        adding the next item would exceed the budget.
    - Non-embeddable list: accumulated in parallel and does not contribute to the
        flush condition.
    Each flush (or end-of-chunk) emits a single combined UPSERT batch from both
    lists (wrapped in a per-chunk transaction in non-dry-runs).

    Args:
        config (EntityConfig): Registry config describing the entity kind,
            ORM table, and traverser.
        dry_run (bool): If True, skip DELETE/UPSERT statements and external
            embedding calls.
        force_index (bool): If True, ignore existing hashes and reindex all
            fields for each entity.
        chunk_size (int): Number of entities to process per batch. Defaults to 1000.

    Notes:
        - Non-dry-run runs open a write session and wrap each processed chunk in
          a transaction (`Session.begin()`).
        - Read queries use the passed session when available, otherwise the
          generic `db.session`.

    Workflow:
        1) Stream entities (yield_per=chunk_size) and accumulate into a chunk.
        2) Begin transaction for the chunk.
        3) determine_changes() → fields_to_upsert, paths_to_delete.
        4) Delete stale paths.
        5) Build UPSERT batches with a two-list buffer:
        - Embeddable list (STRING): track running token count; flush when next item
            would exceed the token budget (model max context - safety margin).
        - Non-embeddable list: accumulate in parallel; does not affect flushing.
        6) Execute UPSERT for each batch (skip in dry_run).
        7) Commit transaction (auto on context exit).
        8) Repeat until the stream is exhausted.
    """

    def __init__(self, config: EntityConfig, dry_run: bool, force_index: bool, chunk_size: int = 1000) -> None:
        self.config = config
        self.dry_run = dry_run
        self.force_index = force_index
        self.chunk_size = chunk_size
        self.embedding_model = llm_settings.EMBEDDING_MODEL
        self.logger = logger.bind(entity_kind=config.entity_kind.value)

    def run(self, entities: Iterable[DatabaseEntity]) -> int:
        """Orchestrates the entire indexing process."""
        chunk: list[DatabaseEntity] = []
        total_records_processed = 0
        total_identical_records = 0

        write_scope = db.database_scope() if not self.dry_run else nullcontext()

        def flush() -> None:
            nonlocal total_records_processed, total_identical_records
            with _maybe_begin(session):
                processed_in_chunk, identical_in_chunk = self._process_chunk(chunk, session)
                total_records_processed += processed_in_chunk
                total_identical_records += identical_in_chunk
            chunk.clear()

        with write_scope as database:
            session: Session | None = getattr(database, "session", None)
            for entity in entities:
                chunk.append(entity)
                if len(chunk) >= self.chunk_size:
                    flush()

            if chunk:
                flush()

        final_log_message = (
            f"processed {total_records_processed} records and skipped {total_identical_records} identical records."
        )
        self.logger.info(
            f"Dry run, would have indexed {final_log_message}"
            if self.dry_run
            else f"Indexing done, {final_log_message}"
        )
        return total_records_processed

    def _process_chunk(self, entity_chunk: list[DatabaseEntity], session: Session | None = None) -> tuple[int, int]:
        """Process a chunk of entities."""
        if not entity_chunk:
            return 0, 0

        fields_to_upsert, paths_to_delete, identical_count = self._determine_changes(entity_chunk, session)

        if paths_to_delete and session is not None:
            self.logger.debug(f"Deleting {len(paths_to_delete)} stale records in chunk.")
            self._execute_batched_deletes(paths_to_delete, session)

        if fields_to_upsert:
            upsert_stmt = self._get_upsert_statement()
            batch_generator = self._generate_upsert_batches(fields_to_upsert)

            for batch in batch_generator:
                if self.dry_run:
                    self.logger.debug(f"Dry Run: Would upsert {len(batch)} records.")
                elif batch and session:
                    session.execute(upsert_stmt, batch)

        return len(fields_to_upsert), identical_count

    def _determine_changes(
        self, entities: list[DatabaseEntity], session: Session | None = None
    ) -> tuple[list[tuple[str, ExtractedField]], list[tuple[str, Ltree]], int]:
        """Identifies all changes across all entities using pre-fetched data."""
        entity_ids = [str(getattr(e, self.config.pk_name)) for e in entities]
        read_session = session or db.session
        existing_hashes = {} if self.force_index else self._get_all_existing_hashes(entity_ids, read_session)

        fields_to_upsert: list[tuple[str, ExtractedField]] = []
        paths_to_delete: list[tuple[str, Ltree]] = []
        identical_records_count = 0

        for entity in entities:
            entity_id = str(getattr(entity, self.config.pk_name))
            current_fields = self.config.traverser.get_fields(
                entity, pk_name=self.config.pk_name, root_name=self.config.root_name
            )

            entity_hashes = existing_hashes.get(entity_id, {})
            current_paths = set()

            for field in current_fields:
                current_paths.add(field.path)
                current_hash = self._compute_content_hash(field.path, field.value, field.value_type)
                if field.path not in entity_hashes or entity_hashes[field.path] != current_hash:
                    fields_to_upsert.append((entity_id, field))
                else:
                    identical_records_count += 1

            stale_paths = set(entity_hashes.keys()) - current_paths
            paths_to_delete.extend([(entity_id, Ltree(p)) for p in stale_paths])

        return fields_to_upsert, paths_to_delete, identical_records_count

    def _execute_batched_deletes(self, paths_to_delete: list[tuple[str, Ltree]], session: Session) -> None:
        """Execute delete operations in batches to avoid PostgreSQL stack depth limits."""
        for i in range(0, len(paths_to_delete), self.chunk_size):
            batch = paths_to_delete[i : i + self.chunk_size]
            delete_stmt = delete(AiSearchIndex).where(tuple_(AiSearchIndex.entity_id, AiSearchIndex.path).in_(batch))
            session.execute(delete_stmt)
            self.logger.debug(f"Deleted batch of {len(batch)} records.")

    def _get_all_existing_hashes(self, entity_ids: list[str], session: Session) -> dict[str, dict[str, str]]:
        """Fetches all existing hashes for a list of entity IDs in a single query."""
        if not entity_ids:
            return {}

        results = (
            session.query(AiSearchIndex.entity_id, AiSearchIndex.path, AiSearchIndex.content_hash)
            .filter(AiSearchIndex.entity_id.in_(entity_ids))
            .all()
        )

        hashes_by_entity: dict[str, dict[str, str]] = {eid: {} for eid in entity_ids}
        for entity_id, path, content_hash in results:
            hashes_by_entity[str(entity_id)][str(path)] = content_hash
        return hashes_by_entity

    def _generate_upsert_batches(
        self, fields_to_upsert: Iterable[tuple[str, ExtractedField]]
    ) -> Generator[list[IndexableRecord], None, None]:
        """Streams through fields, buffers them by token count, and yields batches."""
        embeddable_buffer: list[tuple[str, ExtractedField]] = []
        non_embeddable_records: list[IndexableRecord] = []
        current_tokens = 0

        max_ctx = self._get_max_tokens()
        safe_margin = int(max_ctx * llm_settings.EMBEDDING_SAFE_MARGIN_PERCENT)
        token_budget = max(1, max_ctx - safe_margin)

        max_batch_size = None
        if llm_settings.OPENAI_BASE_URL:  # We are using a local model
            max_batch_size = llm_settings.EMBEDDING_MAX_BATCH_SIZE

        for entity_id, field in fields_to_upsert:
            if field.value_type.is_embeddable(field.value):
                text = self._prepare_text_for_embedding(field)
                try:
                    item_tokens = len(encode(model=self.embedding_model, text=text))
                except Exception as e:
                    self.logger.warning("Tokenization failed; skipping.", path=field.path, err=str(e))
                    continue

                if item_tokens > max_ctx:
                    self.logger.warning(
                        "Field exceeds context; skipping.", path=field.path, tokens=item_tokens, max_ctx=max_ctx
                    )
                    continue

                should_flush = embeddable_buffer and (
                    current_tokens + item_tokens > token_budget
                    or (max_batch_size and len(embeddable_buffer) >= max_batch_size)
                )

                if should_flush:
                    yield self._flush_buffer(embeddable_buffer, non_embeddable_records)
                    embeddable_buffer.clear()
                    non_embeddable_records.clear()
                    current_tokens = 0

                embeddable_buffer.append((entity_id, field))
                current_tokens += item_tokens
            else:
                record = self._make_indexable_record(field, entity_id, embedding=None)
                non_embeddable_records.append(record)

        if embeddable_buffer or non_embeddable_records:
            yield self._flush_buffer(embeddable_buffer, non_embeddable_records)

    def _flush_buffer(self, embeddable_buffer: list, non_embeddable_records: list) -> list[IndexableRecord]:
        """Processes and combines buffers into a single batch."""
        if not embeddable_buffer:
            return non_embeddable_records

        texts_to_embed = [self._prepare_text_for_embedding(f) for _, f in embeddable_buffer]
        embeddings = EmbeddingIndexer.get_embeddings_from_api_batch(texts_to_embed, self.dry_run)

        if len(embeddable_buffer) != len(embeddings):
            raise ValueError(f"Embedding mismatch: sent {len(embeddable_buffer)}, received {len(embeddings)}")

        with_embeddings = [
            self._make_indexable_record(field, entity_id, embedding)
            for (entity_id, field), embedding in zip(embeddable_buffer, embeddings)
        ]
        return non_embeddable_records + with_embeddings

    def _get_max_tokens(self) -> int:
        """Gets max tokens, using a fallback from settings if necessary."""
        try:
            max_ctx = get_max_tokens(self.embedding_model)
            if isinstance(max_ctx, int):
                return max_ctx
        except Exception:
            # Allow local(unknown) models to fall back.
            self.logger.warning("Could not auto-detect max tokens.", model=self.embedding_model)

        max_ctx = llm_settings.EMBEDDING_FALLBACK_MAX_TOKENS
        if not isinstance(max_ctx, int):
            raise RuntimeError("Model not recognized and EMBEDDING_FALLBACK_MAX_TOKENS not set.")
        self.logger.warning("Using configured fallback token limit.", fallback=max_ctx)
        return max_ctx

    @staticmethod
    def _prepare_text_for_embedding(field: ExtractedField) -> str:
        return f"{field.path}: {str(field.value)}"

    @staticmethod
    def _compute_content_hash(path: str, value: Any, value_type: Any) -> str:
        v = "" if value is None else str(value)
        content = f"{path}:{v}:{value_type}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _make_indexable_record(
        self, field: ExtractedField, entity_id: str, embedding: list[float] | None
    ) -> IndexableRecord:
        return IndexableRecord(
            entity_id=entity_id,
            entity_type=self.config.entity_kind.value,
            path=Ltree(field.path),
            value=field.value,
            value_type=field.value_type,
            content_hash=self._compute_content_hash(field.path, field.value, field.value_type),
            embedding=embedding if embedding else None,
        )

    @staticmethod
    @lru_cache(maxsize=1)
    def _get_upsert_statement() -> Insert:
        stmt = insert(AiSearchIndex)
        return stmt.on_conflict_do_update(
            index_elements=[AiSearchIndex.entity_id, AiSearchIndex.path],
            set_={
                AiSearchIndex.value: stmt.excluded.value,
                AiSearchIndex.value_type: stmt.excluded.value_type,
                AiSearchIndex.content_hash: stmt.excluded.content_hash,
                AiSearchIndex.embedding: stmt.excluded.embedding,
            },
        )
