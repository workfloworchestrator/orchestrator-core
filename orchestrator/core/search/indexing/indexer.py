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
from typing import Any

import structlog
from sqlalchemy import delete, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.dialects.postgresql.dml import Insert
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import AiSearchIndex
from orchestrator.core.domain.context_cache import (
    cache_subscription_models,
    evict_from_cache,
    no_subscription_model_cache,
)
from orchestrator.core.search.core.embedding import EmbeddingIndexer
from orchestrator.core.search.core.types import EntityType, ExtractedField, IndexableRecord
from orchestrator.core.search.indexing.registry import EntityConfig
from orchestrator.core.search.indexing.traverse import DatabaseEntity
from orchestrator.core.settings import llm_settings

logger = structlog.get_logger(__name__)

_SEARCH_INDEX_WRITE_LOCK = text(
    "SELECT pg_advisory_xact_lock(hashtext('orchestrator.search.indexer'), hashtext(:entity_type))"
)


def acquire_search_index_write_lock(session: Session, entity_kind: EntityType) -> None:
    """Serialize writes for this entity type within the current transaction.

    The `ai_search_paths` trigger updates shared path rows. A bulk chunk and a
    single-entity chunk can touch those rows in opposite orders and deadlock.
    Entity types use separate locks because their trigger keys cannot overlap.

    The lock is transaction-scoped: it is released when the caller's transaction
    commits, so acquire it in the same transaction as the writes it protects.
    """
    session.execute(_SEARCH_INDEX_WRITE_LOCK, {"entity_type": entity_kind.value})


def _has_external_transaction(session: Session) -> bool:
    """Check an idle Session's bind without opening a connection or autobeginning.

    Call before beginning a Session transaction: an engine binding is owned, whereas
    a bound Connection can already carry a transaction that Session.commit() cannot end.
    """
    bind = session.get_bind()
    return isinstance(bind, Connection) and bind.in_transaction()


@contextmanager
def _maybe_begin(session: Session | None, *, allow_borrow: bool = True) -> Iterator[None]:
    if session is None:
        yield
    elif session.in_transaction():
        if not allow_borrow:
            raise RuntimeError(
                "The write session already has an active transaction that this indexer does not "
                "own: joining it would mean no one ever commits, so every write would silently "
                "roll back when the session scope ends. Most likely the entities iterable lazily "
                "queried db.session while Indexer.run() was setting up its own session — pass a "
                "materialized sequence (list(...)) to run(), or commit per chunk when driving "
                "_process_chunk directly."
            )
        # The caller already owns an open transaction: join it, do not begin or commit.
        yield
    else:
        if not allow_borrow and _has_external_transaction(session):
            raise RuntimeError(
                "The write session is bound to a Connection with an externally begun transaction: "
                "Session.commit() cannot release its advisory locks or guarantee persistence. "
                "Use an engine-bound session or a Connection without an active transaction; "
                "only the caller may commit or roll back the external transaction."
            )
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
        - Writes for the same entity kind are serialized per transaction. This prevents
          concurrent chunks from deadlocking in the `ai_search_paths` maintenance trigger.
        - Upsert batches are built (including embedding API calls) before the lock is
          acquired, so embedding latency is not spent holding the lock. This holds one
          chunk's worth of embedded records in memory before the first write; the chunk's
          fields are already fully materialized by `determine_changes`.
        - Read queries use the passed session when available, otherwise the
          generic `db.session`.

    Workflow:
        1) Stream entities (yield_per=chunk_size) and accumulate into a chunk.
        2) Begin transaction for the chunk.
        3) determine_changes() → fields_to_upsert, paths_to_delete.
        4) Build UPSERT batches with a two-list buffer:
        - Embeddable list (STRING): track running token count; flush when next item
            would exceed the token budget (model max context - safety margin).
        - Non-embeddable list: accumulate in parallel; does not affect flushing.
        5) Acquire an entity-kind write lock when the chunk has changes.
        6) Delete stale paths (skipped in dry_run).
        7) Execute UPSERT for each batch (skip in dry_run).
        8) Commit transaction (auto on context exit).
        9) Repeat until the stream is exhausted.
    """

    def __init__(
        self,
        config: EntityConfig,
        dry_run: bool,
        force_index: bool,
        chunk_size: int = 1000,
        show_progress: bool = False,
        total_count: int | None = None,
    ) -> None:
        self.config = config
        self.dry_run = dry_run
        self.force_index = force_index
        self.chunk_size = chunk_size
        self.show_progress = show_progress
        self.total_count = total_count
        self.embedding_model = llm_settings.EMBEDDING_MODEL
        self.logger = logger.bind(entity_kind=config.entity_kind.value)
        self._entity_titles: dict[str, str] = {}
        self._dropped_entity_ids: set[str] = set()

    def run(self, entities: Iterable[DatabaseEntity]) -> int:
        """Orchestrates the entire indexing process.

        ``entities`` must not lazily query ``db.session`` while being consumed inside
        ``run()`` (e.g. an unfinished ``yield from db.session.scalars(...)``): that
        autobegins the very session ``run()`` intends to own, and the first chunk
        raises instead of writing. Materialize the stream before calling ``run()``.

        The session factory must bind to an engine or a connection without an externally
        begun transaction. External transactions are rejected before chunk planning:
        Session-level commits cannot release their advisory locks or guarantee persistence.
        """
        self._dropped_entity_ids.clear()  # a failed earlier run's drops belong to no one but the next reindex
        chunk: list[DatabaseEntity] = []
        total_records_processed = 0
        total_identical_records = 0

        write_scope = db.database_scope() if not self.dry_run else nullcontext()

        def flush() -> None:
            nonlocal total_records_processed, total_identical_records
            with _maybe_begin(session, allow_borrow=False):
                processed_in_chunk, identical_in_chunk, dropped_in_chunk = self._process_chunk(chunk, session)
                total_records_processed += processed_in_chunk
                total_identical_records += identical_in_chunk
                self._dropped_entity_ids.update(dropped_in_chunk)
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

            if session is not None and not self.dry_run and self._dropped_entity_ids:
                retry_processed, retry_identical = self._retry_dropped(session)
                total_records_processed += retry_processed
                total_identical_records += retry_identical

        final_log_message = (
            f"processed {total_records_processed} records and skipped {total_identical_records} identical records."
        )
        self.logger.info(
            f"Dry run, would have indexed {final_log_message}"
            if self.dry_run
            else f"Indexing done, {final_log_message}"
        )
        return total_records_processed

    def _retry_dropped(self, session: Session) -> tuple[int, int]:
        """Reprocess entities whose prepared work lost the race, exactly once.

        Reloads each partition through the config's own query, inside the transaction that
        is about to write, so the retry plans from state at least as fresh as the drop.
        The inherited subscription model cache is bypassed; each actual planning attempt
        also refreshes ORM state and creates its own model cache after its baseline read.
        Work dropped again by
        revalidation is logged and abandoned: looping on a continuously updated entity would
        starve the run, and the next scheduled reindex picks the leftovers up.

        When the caller owns the transaction (on the Session or its bound Connection),
        the retry is skipped:
        the advisory lock is transaction-scoped, so any lock taken by the first pass is
        still held and the retry's embedding would run under it, blocking same-type hook
        writers. The dropped ids are logged; the next scheduled reindex converges.
        """
        entity_ids = sorted(self._dropped_entity_ids)
        self._dropped_entity_ids.clear()

        borrowed_reason = None
        if session.in_transaction():
            borrowed_reason = "transaction_borrowed"
        elif _has_external_transaction(session):
            borrowed_reason = "external_connection_transaction"

        if borrowed_reason is not None:
            self.logger.warning(
                "Skipped retry of dropped index work: caller transaction still open",
                entity_kind=self.config.entity_kind.value,
                dropped=len(entity_ids),
                dropped_entity_ids=entity_ids,
                reason=borrowed_reason,
            )
            return 0, 0

        processed = 0
        identical = 0
        second_pass_drops: set[str] = set()
        with no_subscription_model_cache():
            for i in range(0, len(entity_ids), self.chunk_size):
                partition = entity_ids[i : i + self.chunk_size]
                with _maybe_begin(session, allow_borrow=False):
                    # Reload inside the transaction: executing before it would autobegin and
                    # the next session.begin() would raise. Only rows still in the source
                    # (config filters included) are retried.
                    rows = self._load_source_entities(partition, session)
                    if rows:
                        chunk_processed, chunk_identical, chunk_dropped = self._process_chunk(rows, session)
                        processed += chunk_processed
                        identical += chunk_identical
                        second_pass_drops.update(chunk_dropped)

        if second_pass_drops:
            self.logger.warning(
                "Dropped stale index work after retry",
                dropped=len(second_pass_drops),
                dropped_entity_ids=sorted(second_pass_drops),
            )

        return processed, identical

    def _process_chunk(
        self, entity_chunk: list[DatabaseEntity], session: Session | None = None
    ) -> tuple[int, int, list[str]]:
        """Process a chunk of entities.

        Returns (processed_records, identical_records, dropped_entity_ids). Dropped ids are
        work that lost the race to a concurrent writer under the lock; ``run()`` collects
        them and performs the single bounded retry pass.

        Direct callers driving this method themselves must end the underlying database
        transaction per chunk (or use ``run()``). Session.commit() alone cannot end an
        external bound-Connection transaction. The advisory lock is transaction-scoped:
        a caller that holds one transaction open across chunks keeps the lock from the
        first acquisition, so later chunks embed under it, and ``_retry_dropped`` skips
        its retry entirely because the first pass's lock is still held.
        """
        if not entity_chunk:
            return 0, 0, []

        self._entity_titles.clear()

        fields_to_upsert, paths_to_delete, identical_count, baseline_hashes = self._determine_changes(
            entity_chunk, session
        )

        # The revalidation's correctness (and the delete/resurrection guards) depend on each
        # statement seeing the latest committed data; fixed-snapshot isolation levels defeat
        # it silently. Reject such sessions before spending embedding calls or taking locks.
        if session is not None and not self.dry_run and (fields_to_upsert or paths_to_delete):
            self._ensure_statement_fresh_isolation(session)

        # Build all batches (embedding API calls happen here) before the lock so external
        # latency does not stall same-type indexers waiting on the advisory lock. Delete-only
        # chunks skip this entirely: they need neither embeddings nor the tokenization setup.
        batches = list(self._generate_upsert_batches(fields_to_upsert)) if fields_to_upsert else []

        dropped_entity_ids: list[str] = []
        if session is not None and not self.dry_run and (fields_to_upsert or paths_to_delete):
            acquire_search_index_write_lock(session, self.config.entity_kind)
            # Prepared work may have gone stale while it was being embedded: a concurrent
            # indexer may have written newer values, or a removal may have deleted rows.
            # Revalidation logs the drop summary by reason.
            batches, paths_to_delete, dropped_entity_ids = self._revalidate_planned_writes(
                batches, paths_to_delete, baseline_hashes, session
            )

        if paths_to_delete and session is not None:
            if self.dry_run:
                self.logger.debug(f"Dry Run: would have deleted {len(paths_to_delete)} stale records.")
            else:
                self.logger.debug(f"Deleting {len(paths_to_delete)} stale records in chunk.")
                self._execute_batched_deletes(paths_to_delete, session)

        if batches:
            upsert_stmt = self._get_upsert_statement()

            for batch in batches:
                if self.dry_run:
                    self.logger.debug(f"Dry Run: Would upsert {len(batch)} records.")
                elif batch and session:
                    session.execute(upsert_stmt, batch)

        return sum(len(batch) for batch in batches), identical_count, dropped_entity_ids

    @staticmethod
    def _reject_pending_changes(session: Session) -> None:
        """Require a clean planning session before any autoflush-capable read.

        The source-fresh reload refreshes eager-loaded related rows as well as roots.
        Restricting this check to planned roots would silently discard related edits;
        checking after a query would instead let autoflush hide the pending changes.
        """
        if len(session.dirty) or len(session.new) or len(session.deleted):
            raise RuntimeError(
                "The planning session has pending, unflushed changes; flush before indexing "
                "or plan from a clean session. The fresh reload also refreshes related rows "
                "and could discard pending edits."
            )

    def _ensure_statement_fresh_isolation(self, session: Session) -> None:
        """Require statement-fresh PostgreSQL isolation for the under-lock recheck.

        PostgreSQL implements READ UNCOMMITTED with READ COMMITTED semantics.
        Under REPEATABLE READ the transaction snapshot is fixed at the first read: the
        under-lock recheck would still see the pre-baseline world, admitting stale upserts
        and resurrecting entities deleted (and hook-removal-indexed) after planning — with
        no serialization error to surface it. The application never pins an isolation
        level, so a database or role default can set it silently; refuse such sessions
        instead of indexing unsafely.
        """
        connection = session.connection()
        # get_isolation_level() reports the server's isolation, NOT DBAPI AUTOCOMMIT.
        # Both supported PostgreSQL drivers expose their actual mode via this flag.
        dbapi_connection = connection.connection.dbapi_connection
        if dbapi_connection is not None and dbapi_connection.autocommit is True:
            raise RuntimeError(
                "Indexing requires a transaction-scoped advisory lock; DBAPI AUTOCOMMIT "
                "releases that lock after its statement and is unsupported."
            )
        level = connection.get_isolation_level()
        if isinstance(level, str) and level.strip().upper() not in {"READ COMMITTED", "READ UNCOMMITTED"}:
            raise RuntimeError(
                f"Indexing requires READ COMMITTED or READ UNCOMMITTED, found {level!r}: the under-lock "
                "revalidation must see data committed after the plan's baseline read, which fixed-"
                "snapshot isolation levels cannot."
            )

    def _load_source_entities(self, entity_ids: list[str], session: Session) -> list[DatabaseEntity]:
        """Reload entities through the config's own query.

        Filters (e.g. soft-delete), column types and eager loads are exactly what the indexer
        would see on a fresh run, so plans are never built from a stale stream snapshot.
        """
        if not entity_ids:
            return []
        self._reject_pending_changes(session)
        pk_column = getattr(self.config.table, self.config.pk_name)
        stmt = (
            self.config.get_all_query(None).where(pk_column.in_(entity_ids)).execution_options(populate_existing=True)
        )
        rows = list(session.execute(stmt).scalars().all())
        if self.config.entity_kind == EntityType.SUBSCRIPTION:
            # SubscriptionTraverser rebuilds models via SubscriptionModel.from_subscription(),
            # which prefers a model cached earlier in the run over the database. Evict the ids
            # about to be planned so traversal sees the state this reload just read.
            #
            # Note: from_subscription() reads rows through the AMBIENT db.session, so
            # subscription planning is only correct on that session — which run() always
            # is. Direct callers planning on a foreign session do not get aligned
            # transaction visibility here or in the traverser.
            evict_from_cache(entity_ids)
        return rows

    @contextmanager
    def _planning_model_cache(self, session: Session | None) -> Iterator[None]:
        """Isolate subscription ORM/domain state read after this attempt's baseline.

        Domain-cache bypass alone can rebuild models from a stale pinned ORM object.
        Expire only the clean planning Session, never a different ambient Session.
        Dependencies loaded during this attempt may be shared within it, not with
        earlier chunks or retry attempts. The caller's outer domain cache is restored.
        """
        if session is None or self.dry_run or self.config.entity_kind != EntityType.SUBSCRIPTION:
            yield
            return

        self._reject_pending_changes(session)
        session.expire_all()
        with cache_subscription_models(fresh=True):
            yield

    def _determine_changes(
        self, entities: list[DatabaseEntity], session: Session | None = None
    ) -> tuple[list[tuple[str, ExtractedField]], list[tuple[str, Ltree]], int, dict[str, dict[str, str]]]:
        """Identifies all changes across all entities using pre-fetched data.

        Returns (fields_to_upsert, paths_to_delete, identical_count, baseline_hashes). The
        baseline hash map is the stored state this plan was derived from; callers pass it to
        ``_revalidate_planned_writes`` under the write lock. Force mode forces every field
        into the plan but still reads real baselines, so a drifted row is repaired, not dropped.
        """
        read_session = session or db.session
        if session is not None and not self.dry_run:
            self._reject_pending_changes(read_session)

        # Dry-run must not turn reads (including expired attributes and traversal's
        # relationship queries) into DML by autoflushing caller-owned pending changes.
        with read_session.no_autoflush if self.dry_run else nullcontext():
            entity_ids = [str(getattr(e, self.config.pk_name)) for e in entities]
            existing_hashes = self._get_all_existing_hashes(entity_ids, read_session)

            # Baseline first, then fresh ORM AND domain state. Pre-baseline dependency
            # cache hits can otherwise downgrade an already-newer computed path even
            # when the source root is freshly populated and the index never changes back.
            with self._planning_model_cache(session):
                if session is not None and not self.dry_run:
                    fresh = self._load_source_entities(entity_ids, read_session)
                    fresh_ids = {str(getattr(entity, self.config.pk_name)) for entity in fresh}
                    if len(fresh_ids) != len(entity_ids):
                        self.logger.info(
                            "Skipped entities that disappeared before planning",
                            entity_kind=self.config.entity_kind.value,
                            missing=len(set(entity_ids) - fresh_ids),
                        )
                    entities = fresh

                fields_to_upsert: list[tuple[str, ExtractedField]] = []
                paths_to_delete: list[tuple[str, Ltree]] = []
                identical_records_count = 0

                for entity in entities:
                    entity_id = str(getattr(entity, self.config.pk_name))
                    current_fields = self.config.traverser.get_fields(
                        entity, pk_name=self.config.pk_name, root_name=self.config.root_name
                    )

                    entity_title = self.config.get_title_from_fields(current_fields)
                    self._entity_titles[entity_id] = entity_title

                    entity_hashes = existing_hashes.get(entity_id, {})
                    current_paths = set()

                    for field in current_fields:
                        current_paths.add(field.path)
                        current_hash = self._compute_content_hash(
                            field.path, field.value, field.value_type, entity_title
                        )
                        if (
                            self.force_index
                            or field.path not in entity_hashes
                            or entity_hashes[field.path] != current_hash
                        ):
                            fields_to_upsert.append((entity_id, field))
                        else:
                            identical_records_count += 1

                    if not self.force_index:
                        # Force mode rebuilds values; removing index rows for paths the entity no
                        # longer exposes stays a plain-reindex behavior.
                        stale_paths = set(entity_hashes.keys()) - current_paths
                        paths_to_delete.extend([(entity_id, Ltree(p)) for p in stale_paths])

                return fields_to_upsert, paths_to_delete, identical_records_count, existing_hashes

    def _fetch_alive_ids(self, entity_ids: list[str], session: Session) -> set[str]:
        """Return the subset of ``entity_ids`` that is still indexable in the source.

        Built on the config's own query so its filters apply (e.g. workflows soft-delete
        via ``deleted_at``), and ids bind as the strings the indexer keys on — schedule ids
        live in a string column and PostgreSQL has no varchar-vs-uuid comparison.
        """
        if not entity_ids:
            return set()
        # with_only_columns keeps the config query's FROM and filters (soft-delete included)
        # while projecting just the pk column object itself — so ids bind with the column's own
        # type (no UUID coercion for string schedule ids) and synonym-named pks (process pid)
        # resolve to their real column.
        pk_column = getattr(self.config.table, self.config.pk_name)
        stmt = self.config.get_all_query(None).with_only_columns(pk_column).where(pk_column.in_(entity_ids))
        rows = session.execute(stmt).all()
        return {str(row[0]) for row in rows}

    def _stale_upsert_reason(
        self,
        record: IndexableRecord,
        alive: set[str],
        stored: dict[str, dict[str, str]],
        baseline_hashes: dict[str, dict[str, str]],
    ) -> str | None:
        """Why this prepared upsert must not be written, or None when it is still valid.

        ``stored`` is the under-lock state and ``baseline_hashes`` the state the plan was
        derived from. A stored value that differs from both means a third writer won.

        Known limitation: content hashes establish value equality, not write ordering. If a
        value changes and then changes back to the baseline value within the comparison
        interval — from the baseline read under this chunk's transaction through the
        under-lock recheck, spanning the source reload, traversal, embedding and any wait
        for the advisory lock (which can be long even with no embedding at all) — the
        stored hash again equals the baseline and the prepared write is admitted. The index
        may converge on a later fresh hook write or scheduled reindex. Such admitted
        work is not detected or retried. Stronger write-order/source validation requires
        a separate design; hashes alone cannot establish it.
        """
        entity_id = record["entity_id"]
        if entity_id not in alive:
            # Entity was deleted after we read it; writing would resurrect its row.
            return "entity_deleted"
        baseline = baseline_hashes.get(entity_id, {}).get(str(record["path"]))
        current = stored.get(entity_id, {}).get(str(record["path"]))
        if current is None and baseline is not None:
            # Its index row was removed since planning; do not resurrect it.
            return "row_removed_since_planning"
        if current is not None and current not in (record["content_hash"], baseline):
            # A third writer indexed a different, newer value in the meantime.
            return "overwritten_by_newer"
        return None

    def _revalidate_planned_writes(
        self,
        batches: list[list[IndexableRecord]],
        paths_to_delete: list[tuple[str, Ltree]],
        baseline_hashes: dict[str, dict[str, str]],
        session: Session,
    ) -> tuple[list[list[IndexableRecord]], list[tuple[str, Ltree]], list[str]]:
        """Re-check prepared work against the state stored under the write lock.

        The chunk was planned at T0 and embedded outside the lock; meanwhile a single-entity
        indexer may have indexed newer values, or a removal may have deleted rows. Call this
        after ``acquire_search_index_write_lock`` and before writing. Returns the operations
        that are still valid plus the entity ids whose dropped upserts deserve a retry
        (cancelled deletes do not: there is nothing newer to index).
        """
        if not batches and not paths_to_delete:
            return batches, paths_to_delete, []

        entity_ids = sorted(
            {record["entity_id"] for batch in batches for record in batch}
            | {entity_id for entity_id, _ in paths_to_delete}
        )
        stored = self._get_all_existing_hashes(entity_ids, session)
        alive = self._fetch_alive_ids(entity_ids, session)

        dropped_entity_ids: set[str] = set()
        counts: dict[str, int] = {"overwritten_by_newer": 0, "entity_deleted": 0, "row_removed_since_planning": 0}
        kept_batches: list[list[IndexableRecord]] = []
        for batch in batches:
            kept_batch: list[IndexableRecord] = []
            for record in batch:
                reason = self._stale_upsert_reason(record, alive, stored, baseline_hashes)
                if reason is None:
                    kept_batch.append(record)
                else:
                    dropped_entity_ids.add(record["entity_id"])
                    counts[reason] += 1
            if kept_batch:
                kept_batches.append(kept_batch)

        kept_deletes = []
        delete_cancelled = 0
        for entity_id, path in paths_to_delete:
            if self._delete_was_cancelled(entity_id, str(path), baseline_hashes, stored):
                delete_cancelled += 1
            else:
                kept_deletes.append((entity_id, path))

        if delete_cancelled or any(counts.values()):
            self.logger.info(
                "Dropped stale index work under lock",
                entity_kind=self.config.entity_kind.value,
                delete_cancelled=delete_cancelled,
                **counts,
            )
        return kept_batches, kept_deletes, sorted(dropped_entity_ids)

    @staticmethod
    def _delete_was_cancelled(
        entity_id: str,
        path: str,
        baseline_hashes: dict[str, dict[str, str]],
        stored: dict[str, dict[str, str]],
    ) -> bool:
        """Cancel a planned delete when a changed hash reveals a reindex after T0.

        Cancellation is detected by hash change, so — like the upsert rule above — a path
        re-indexed to a hash equal to its baseline is indistinguishable from never having
        changed, and the delete proceeds. Same hash-equality-not-ordering limitation.
        """
        baseline = baseline_hashes.get(entity_id, {}).get(path)
        current = stored.get(entity_id, {}).get(path)
        return baseline is not None and current is not None and current != baseline

    def _execute_batched_deletes(self, paths_to_delete: list[tuple[str, Ltree]], session: Session) -> None:
        """Execute delete operations in batches to avoid PostgreSQL stack depth limits."""
        for i in range(0, len(paths_to_delete), self.chunk_size):
            batch = paths_to_delete[i : i + self.chunk_size]
            delete_stmt = (
                delete(AiSearchIndex)
                .where(AiSearchIndex.entity_type == self.config.entity_kind.value)
                .where(tuple_(AiSearchIndex.entity_id, AiSearchIndex.path).in_(batch))
            )
            session.execute(delete_stmt)
            self.logger.debug(f"Deleted batch of {len(batch)} records.")

    def _get_all_existing_hashes(self, entity_ids: list[str], session: Session) -> dict[str, dict[str, str]]:
        """Fetches all existing hashes for a list of entity IDs in a single query."""
        if not entity_ids:
            return {}

        results = session.execute(
            select(AiSearchIndex.entity_id, AiSearchIndex.path, AiSearchIndex.content_hash).where(
                AiSearchIndex.entity_id.in_(entity_ids),
                # Keep the scan scoped to this indexer's entity type: rows of other types
                # would be misread as stale paths and deleted without their type's lock.
                AiSearchIndex.entity_type == self.config.entity_kind.value,
            )
        ).all()

        hashes_by_entity: dict[str, dict[str, str]] = {eid: {} for eid in entity_ids}
        for entity_id, path, content_hash in results:
            hashes_by_entity[str(entity_id)][str(path)] = content_hash
        return hashes_by_entity

    def _generate_upsert_batches(
        self, fields_to_upsert: Iterable[tuple[str, ExtractedField]]
    ) -> Generator[list[IndexableRecord], None, None]:
        """Streams through fields, buffers them by token count, and yields batches."""
        # Imported lazily because importing litellm is expensive (multiple seconds).
        from litellm.utils import encode

        embeddable_buffer: list[tuple[str, ExtractedField]] = []
        non_embeddable_records: list[IndexableRecord] = []
        current_tokens = 0

        max_ctx = self._get_max_tokens()
        safe_margin = int(max_ctx * llm_settings.EMBEDDING_SAFE_MARGIN_PERCENT)
        token_budget = max(1, max_ctx - safe_margin)

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
        self, field: ExtractedField, entity_id: str, embedding: list[float] | None
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
            embedding=embedding if embedding else None,
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
                AiSearchIndex.embedding: stmt.excluded.embedding,
            },
        )
