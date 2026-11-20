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

import hashlib
from collections.abc import Generator, Iterable, Iterator
from contextlib import contextmanager, nullcontext
from functools import lru_cache
from operator import itemgetter
from typing import Any, NamedTuple

import structlog
from more_itertools import chunked
from sqlalchemy import delete, exists, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.postgresql.dml import Insert
from sqlalchemy.orm import Session
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchEmbedding, AiSearchIndex
from orchestrator.core.search.core.embedding import EmbeddingIndexer, compute_embedding_hash
from orchestrator.core.search.core.types import EmbeddingRecord, ExtractedField, IndexableRecord
from orchestrator.core.search.indexing.registry import EntityConfig
from orchestrator.core.search.indexing.traverse import DatabaseEntity
from orchestrator.core.settings import llm_settings

logger = structlog.get_logger(__name__)


class IndexBatch(NamedTuple):
    """What one flush writes: the index rows, and the vectors they point at that are not stored yet."""

    records: list[IndexableRecord]
    embeddings: list[EmbeddingRecord]


class StoredHashes(NamedTuple):
    """The hashes stored on an existing index row."""

    content_hash: str
    embedding_hash: str | None


@contextmanager
def _maybe_begin(session: Session | None) -> Iterator[None]:
    if session is None:
        yield
    else:
        with session.begin():
            yield


@contextmanager
def _maybe_progress(show_progress: bool, total_count: int | None, label: str) -> Iterator[Any]:
    """Context manager that optionally creates a progress bar."""
    if show_progress:
        import typer

        bar: Any = typer.progressbar(
            length=total_count,
            label=label,
            show_eta=True,
            show_percent=bool(total_count),
        )
        with bar as progress:
            yield progress
    else:
        yield None


class Indexer:
    """Index entities into `AiSearchIndex` using streaming reads and batched writes.

    Entities are read from a streaming iterator and accumulated into chunks of
    size `chunk_size`. For each chunk, the indexer extracts fields, diffs via
    content hashes, deletes stale paths, and prepares upserts. `embedding_hash`
    points an embeddable field at its vector, so only distinct unseen texts go to
    the embedding API. They are buffered against a token budget (model context
    window minus a safety margin) and flushed when the next text would exceed it.

    Each flush (or end-of-chunk) emits an `IndexBatch`. New vectors are inserted before
    the rows that reference them, in the same chunk transaction. A failed text keeps
    its row with the hash, so the next run embeds it again.

    Args:
        config (EntityConfig): Registry config describing the entity kind,
            ORM table, and traverser.
        dry_run (bool): If True, skip DELETE/UPSERT statements and external
            embedding calls.
        force_index (bool): If True, ignore existing hashes and reindex all
            fields for each entity.
        chunk_size (int): Number of entities to process per batch. Defaults to 1000.
        cleanup_orphans (bool): If True, delete unreferenced embeddings after a full run of the entity type.

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
        5) Build batches: buffer the distinct unseen texts of embeddable fields and track
            a running token count, flushing when the next text would exceed the token
            budget (model max context - safety margin). All other records accumulate in
            parallel and do not affect flushing.
        6) Insert the new vectors of each batch, then UPSERT its index rows (skip in dry_run).
        7) Commit transaction (auto on context exit).
        8) Repeat until the stream is exhausted.
        9) If `cleanup_orphans`, delete the embeddings that no index row points at (skip in dry_run).
    """

    def __init__(
        self,
        config: EntityConfig,
        dry_run: bool,
        force_index: bool,
        chunk_size: int = 1000,
        show_progress: bool = False,
        total_count: int | None = None,
        cleanup_orphans: bool = False,
    ) -> None:
        self.config = config
        self.cleanup_orphans = cleanup_orphans
        self.dry_run = dry_run
        self.force_index = force_index
        self.chunk_size = chunk_size
        self.show_progress = show_progress
        self.total_count = total_count
        self.embedding_model = llm_settings.EMBEDDING_MODEL
        self.logger = logger.bind(entity_kind=config.entity_kind.value)
        self._entity_titles: dict[str, str] = {}

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

            with _maybe_progress(
                self.show_progress, self.total_count, f"Indexing {self.config.entity_kind.value}"
            ) as progress:
                for entity in entities:
                    chunk.append(entity)

                    if len(chunk) >= self.chunk_size:
                        flush()
                        if progress:
                            progress.update(self.chunk_size)

                if chunk:
                    flush()
                    if progress:
                        progress.update(len(chunk))

            self._cleanup_orphan_embeddings(session)

        final_log_message = (
            f"processed {total_records_processed} records and skipped {total_identical_records} identical records."
        )
        self.logger.info(
            f"Dry run, would have indexed {final_log_message}"
            if self.dry_run
            else f"Indexing done, {final_log_message}"
        )
        return total_records_processed

    def _cleanup_orphan_embeddings(self, session: Session | None) -> None:
        if session is None or not self.cleanup_orphans:
            return
        with session.begin():
            deleted = self._delete_orphan_embeddings(session)
        self.logger.debug(f"Deleted {deleted} orphan embeddings.")

    def _delete_orphan_embeddings(self, session: Session) -> int:
        """Delete the embeddings of this run's entity type that no index row references.

        Scoped to the entity type because a run only sees the index rows of its own type. A concurrent run's reused
        orphan can be deleted here, the next run heals it by embedding the text again.

        Returns:
            The number of embeddings deleted.
        """
        referenced = exists().where(
            AiSearchIndex.entity_type == AiSearchEmbedding.entity_type,
            AiSearchIndex.embedding_hash == AiSearchEmbedding.embedding_hash,
        )
        result = session.execute(
            delete(AiSearchEmbedding).where(AiSearchEmbedding.entity_type == self.config.entity_kind.value, ~referenced)
        )
        return result.rowcount  # type: ignore[attr-defined]

    def _process_chunk(self, entity_chunk: list[DatabaseEntity], session: Session | None = None) -> tuple[int, int]:
        """Process a chunk of entities."""
        if not entity_chunk:
            return 0, 0

        self._entity_titles.clear()

        fields_to_upsert, paths_to_delete, identical_count = self._determine_changes(entity_chunk, session)

        if paths_to_delete and session is not None:
            self.logger.debug(f"Deleting {len(paths_to_delete)} stale records in chunk.")
            self._execute_batched_deletes(paths_to_delete, session)

        if fields_to_upsert:
            upsert_stmt = self._get_upsert_statement()
            embedding_stmt = self._get_embedding_insert_statement()
            batch_generator = self._generate_upsert_batches(fields_to_upsert, session)

            # A side effect per batch: the generator is lazy and each batch must be written before the next is built.
            for batch in batch_generator:
                self._write_batch(batch, session, upsert_stmt, embedding_stmt)

        return len(fields_to_upsert), identical_count

    def _write_batch(
        self, batch: IndexBatch, session: Session | None, upsert_stmt: Insert, embedding_stmt: Insert
    ) -> None:
        if self.dry_run:
            self.logger.debug(f"Dry Run: Would upsert {len(batch.records)} records.")
        elif session:
            if batch.embeddings:
                # Runs overlap, for example the hook of a finished process and `index all`. Sorted so they lock shared
                # new hashes in the same order and cannot deadlock inside one statement. Across batches they can
                # still wait for each other.
                session.execute(embedding_stmt, sorted(batch.embeddings, key=itemgetter("embedding_hash")))
            if batch.records:
                session.execute(upsert_stmt, batch.records)

    def _determine_changes(
        self, entities: list[DatabaseEntity], session: Session | None = None
    ) -> tuple[list[tuple[str, ExtractedField]], list[tuple[str, Ltree]], int]:
        """Identifies all changes across all entities using pre-fetched data."""
        entity_ids = [str(getattr(e, self.config.pk_name)) for e in entities]
        read_session = session or db.session
        existing_hashes = {} if self.force_index else self._get_all_existing_hashes(entity_ids, read_session)

        fields_by_entity = self._extract_fields(entities)
        titles = {
            entity_id: self.config.get_title_from_fields(fields) for entity_id, fields in fields_by_entity.items()
        }
        self._entity_titles.update(titles)

        stored_embedding_hashes = self._stored_hashes_of_embeddable_fields(fields_by_entity, read_session)

        fields_to_upsert = self._changed_fields(fields_by_entity, titles, existing_hashes, stored_embedding_hashes)
        paths_to_delete = self._stale_paths(fields_by_entity, existing_hashes)
        identical_records_count = sum(len(fields) for fields in fields_by_entity.values()) - len(fields_to_upsert)

        return fields_to_upsert, paths_to_delete, identical_records_count

    def _extract_fields(self, entities: list[DatabaseEntity]) -> dict[str, list[ExtractedField]]:
        """The fields of each entity by entity ID."""
        return {
            str(getattr(entity, self.config.pk_name)): self.config.traverser.get_fields(
                entity, pk_name=self.config.pk_name, root_name=self.config.root_name
            )
            for entity in entities
        }

    def _changed_fields(
        self,
        fields_by_entity: dict[str, list[ExtractedField]],
        titles: dict[str, str],
        existing_hashes: dict[str, dict[str, StoredHashes]],
        stored_embedding_hashes: set[str] | None,
    ) -> list[tuple[str, ExtractedField]]:
        """The `(entity_id, field)` pairs that must be written again."""
        return [
            (entity_id, field)
            for entity_id, fields in fields_by_entity.items()
            for field in fields
            if self._is_changed(
                field, titles[entity_id], existing_hashes.get(entity_id, {}).get(field.path), stored_embedding_hashes
            )
        ]

    @staticmethod
    def _stale_paths(
        fields_by_entity: dict[str, list[ExtractedField]], existing_hashes: dict[str, dict[str, StoredHashes]]
    ) -> list[tuple[str, Ltree]]:
        """The `(entity_id, path)` pairs stored for an entity whose fields no longer have that path."""
        return [
            (entity_id, Ltree(path))
            for entity_id, fields in fields_by_entity.items()
            for path in set(existing_hashes.get(entity_id, {})) - {field.path for field in fields}
        ]

    def _stored_hashes_of_embeddable_fields(
        self, fields_by_entity: dict[str, list[ExtractedField]], session: Session
    ) -> set[str] | None:
        """The stored vector hashes among the embeddable fields, or None when a missing vector is not a change.

        None without a working API (a missing vector is expected) and with force_index (every row is rewritten).
        """
        if not llm_settings.EMBEDDING_API_ENABLED or self.dry_run or self.force_index:
            return None
        return self._existing_embedding_hashes(
            {
                self._embedding_hash(field)
                for fields in fields_by_entity.values()
                for field in fields
                if field.value_type.is_embeddable(field.value)
            },
            session,
        )

    def _is_changed(
        self, field: ExtractedField, title: str, stored: StoredHashes | None, stored_embedding_hashes: set[str] | None
    ) -> bool:
        """Whether a field must be written again, given its stored hashes and the vectors that exist."""
        if stored is None:
            return True
        if stored.content_hash != self._compute_content_hash(field.path, field.value, field.value_type, title):
            return True
        if stored_embedding_hashes is None or not field.value_type.is_embeddable(field.value):
            return False
        current = self._embedding_hash(field)
        return stored.embedding_hash != current or current not in stored_embedding_hashes

    def _execute_batched_deletes(self, paths_to_delete: list[tuple[str, Ltree]], session: Session) -> None:
        """Execute delete operations in batches to avoid PostgreSQL stack depth limits."""
        for i in range(0, len(paths_to_delete), self.chunk_size):
            batch = paths_to_delete[i : i + self.chunk_size]
            delete_stmt = delete(AiSearchIndex).where(tuple_(AiSearchIndex.entity_id, AiSearchIndex.path).in_(batch))
            session.execute(delete_stmt)
            self.logger.debug(f"Deleted batch of {len(batch)} records.")

    def _get_all_existing_hashes(self, entity_ids: list[str], session: Session) -> dict[str, dict[str, StoredHashes]]:
        """Fetches all existing hashes for a list of entity IDs in a single query."""
        if not entity_ids:
            return {}

        results = session.execute(
            select(
                AiSearchIndex.entity_id, AiSearchIndex.path, AiSearchIndex.content_hash, AiSearchIndex.embedding_hash
            ).where(AiSearchIndex.entity_id.in_(entity_ids))
        ).all()

        hashes_by_entity: dict[str, dict[str, StoredHashes]] = {eid: {} for eid in entity_ids}
        for entity_id, path, content_hash, embedding_hash in results:
            hashes_by_entity[str(entity_id)][str(path)] = StoredHashes(content_hash, embedding_hash)
        return hashes_by_entity

    def _embedding_hash(self, field: ExtractedField) -> str:
        """The hash that identifies the vector of an embeddable field."""
        return compute_embedding_hash(self.embedding_model, self._prepare_text_for_embedding(field))

    def _existing_embedding_hashes(self, hashes: set[str], session: Session) -> set[str]:
        """The subset of `hashes` that has a stored vector for this entity type."""

        def stored(batch: list[str]) -> set[str]:
            return set(
                session.scalars(
                    select(AiSearchEmbedding.embedding_hash).where(
                        AiSearchEmbedding.entity_type == self.config.entity_kind.value,
                        AiSearchEmbedding.embedding_hash.in_(batch),
                    )
                )
            )

        return {found for batch in chunked(sorted(hashes), self.chunk_size) for found in stored(batch)}

    def _generate_upsert_batches(
        self, fields_to_upsert: Iterable[tuple[str, ExtractedField]], session: Session | None = None
    ) -> Generator[IndexBatch, None, None]:
        """Buffers the distinct unseen texts by token count and yields batches of records plus new vectors.

        Without a session every text counts as unseen. A text that is stored or buffered already costs no API call.
        """
        fields = list(fields_to_upsert)
        embeddable_hashes = {
            self._embedding_hash(field) for _, field in fields if field.value_type.is_embeddable(field.value)
        }
        handled = self._existing_embedding_hashes(embeddable_hashes, session) if session else set()

        pending_texts: dict[str, str] = {}
        records: list[IndexableRecord] = []
        current_tokens = 0

        max_ctx = self._get_max_tokens()
        safe_margin = int(max_ctx * llm_settings.EMBEDDING_SAFE_MARGIN_PERCENT)
        token_budget = max(1, max_ctx - safe_margin)

        max_batch_size = llm_settings.EMBEDDING_MAX_BATCH_SIZE

        for entity_id, field, embedding_hash, item_tokens in self._price_fields(fields, handled, max_ctx):
            if item_tokens is None:
                records.append(self._make_indexable_record(field, entity_id, embedding_hash))
            else:
                if pending_texts and (
                    current_tokens + item_tokens > token_budget
                    or (max_batch_size and len(pending_texts) >= max_batch_size)
                ):
                    yield self._flush_buffer(pending_texts, records)
                    pending_texts = {}
                    records = []
                    current_tokens = 0

                pending_texts[str(embedding_hash)] = self._prepare_text_for_embedding(field)
                current_tokens += item_tokens
                records.append(self._make_indexable_record(field, entity_id, embedding_hash))

        if pending_texts or records:
            yield self._flush_buffer(pending_texts, records)

    def _price_fields(
        self, fields: list[tuple[str, ExtractedField]], handled: set[str], max_ctx: int
    ) -> Iterator[tuple[str, ExtractedField, str | None, int | None]]:
        """Yields `(entity_id, field, embedding_hash, tokens)` and drops fields that cannot be embedded.

        `tokens` is None when no new vector is needed. A text joins `handled` when its first field is yielded.
        """
        # Not a comprehension: `handled` is read while it is built, as it decides whether the next field is counted.
        for entity_id, field in fields:
            embedding_hash = self._embedding_hash(field) if field.value_type.is_embeddable(field.value) else None
            if embedding_hash is None or embedding_hash in handled:
                yield entity_id, field, embedding_hash, None
            else:
                item_tokens = self._count_tokens(field, max_ctx)
                if item_tokens is not None:
                    handled.add(embedding_hash)
                    yield entity_id, field, embedding_hash, item_tokens

    def _count_tokens(self, field: ExtractedField, max_ctx: int) -> int | None:
        """The token count of the text of a field, or None when the field cannot be embedded and is skipped."""
        # Imported lazily because importing litellm is expensive (multiple seconds).
        from litellm.utils import encode

        try:
            item_tokens = len(encode(model=self.embedding_model, text=self._prepare_text_for_embedding(field)))
        except Exception as e:
            self.logger.warning("Tokenization failed; skipping.", path=field.path, err=str(e))
            return None

        if item_tokens > max_ctx:
            self.logger.warning(
                "Field exceeds context; skipping.", path=field.path, tokens=item_tokens, max_ctx=max_ctx
            )
            return None
        return item_tokens

    def _flush_buffer(self, pending_texts: dict[str, str], records: list[IndexableRecord]) -> IndexBatch:
        """Embeds the buffered texts and combines them with the buffered records into one batch.

        Returns:
            The batch. A text whose vector came back empty gets no embedding, its records still carry the hash.

        Raises:
            ValueError: If the API returns another number of vectors than texts.
        """
        if not pending_texts:
            return IndexBatch(records, [])

        vectors = EmbeddingIndexer.get_embeddings_from_api_batch(list(pending_texts.values()), self.dry_run)

        if len(pending_texts) != len(vectors):
            raise ValueError(f"Embedding mismatch: sent {len(pending_texts)}, received {len(vectors)}")

        entity_type = self.config.entity_kind.value
        embeddings = [
            EmbeddingRecord(entity_type=entity_type, embedding_hash=embedding_hash, embedding=vector)
            for embedding_hash, vector in zip(pending_texts, vectors)
            if vector
        ]
        return IndexBatch(records, embeddings)

    def _get_max_tokens(self) -> int:
        """Gets max tokens, using a fallback from settings if necessary."""
        # Imported lazily because importing litellm is expensive (multiple seconds).
        from litellm.utils import get_max_tokens

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
    def _compute_content_hash(path: str, value: Any, value_type: Any, entity_title: str = "") -> str:
        v = "" if value is None else str(value)
        content = f"{path}:{v}:{value_type}:{entity_title}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _make_indexable_record(
        self, field: ExtractedField, entity_id: str, embedding_hash: str | None
    ) -> IndexableRecord:
        entity_title = self._entity_titles[entity_id]
        return IndexableRecord(
            entity_id=entity_id,
            entity_type=self.config.entity_kind.value,
            entity_title=entity_title,
            path=Ltree(field.path),
            value=field.value,
            value_type=field.value_type,
            content_hash=self._compute_content_hash(field.path, field.value, field.value_type, entity_title),
            embedding_hash=embedding_hash,
        )

    @staticmethod
    @lru_cache(maxsize=1)
    def _get_upsert_statement() -> Insert:
        stmt = insert(AiSearchIndex)
        return stmt.on_conflict_do_update(
            index_elements=[AiSearchIndex.entity_id, AiSearchIndex.path],
            set_={
                AiSearchIndex.entity_title: stmt.excluded.entity_title,
                AiSearchIndex.value: stmt.excluded.value,
                AiSearchIndex.value_type: stmt.excluded.value_type,
                AiSearchIndex.content_hash: stmt.excluded.content_hash,
                AiSearchIndex.embedding_hash: stmt.excluded.embedding_hash,
            },
        )

    @staticmethod
    @lru_cache(maxsize=1)
    def _get_embedding_insert_statement() -> Insert:
        # A concurrent run may have stored the same text, and both vectors are equally valid.
        return insert(AiSearchEmbedding).on_conflict_do_nothing()
