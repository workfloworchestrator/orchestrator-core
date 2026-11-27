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

"""Integration tests for the trigger-maintained ai_search_paths distinct-paths table."""

import time
from contextlib import nullcontext
from threading import Barrier, BrokenBarrierError, Thread
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, event, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.models import (
    AiSearchIndex,
    APSchedulerJobStoreModel,
    SubscriptionTable,
    WorkflowApschedulerJob,
    WorkflowTable,
)
from orchestrator.core.domain.base import SubscriptionModel
from orchestrator.core.domain.context_cache import cache_subscription_models
from orchestrator.core.search.core.types import EntityType, ExtractedField, FieldType, IndexableRecord
from orchestrator.core.search.indexing import rebuild_search_paths
from orchestrator.core.search.indexing.indexer import Indexer, _maybe_begin, acquire_search_index_write_lock
from orchestrator.core.search.indexing.registry import ENTITY_CONFIG_REGISTRY
from orchestrator.core.search.indexing.tasks import _remove_entity_from_index
from orchestrator.core.search.query.builder import build_paths_query, process_path_rows
from orchestrator.core.targets import Target
from orchestrator.core.utils.datetime import nowtz


def _add_index_row(
    path: str,
    *,
    value_type: FieldType = FieldType.STRING,
    entity_type: str = "SUBSCRIPTION",
    entity_id: UUID | None = None,
    value: str = "v",
) -> UUID:
    """Insert one ai_search_index row (fires the maintain trigger) and return its entity_id."""
    eid = entity_id or uuid4()
    db.session.add(
        AiSearchIndex(
            entity_type=entity_type,
            entity_id=eid,
            path=Ltree(path),
            value=value,
            content_hash="0" * 64,
            value_type=value_type,
        )
    )
    db.session.flush()
    return eid


def _refcount(path: str, value_type: FieldType, entity_type: str = "SUBSCRIPTION") -> int | None:
    """Return the refcount for a tuple in ai_search_paths, or None if the row is absent."""
    row = db.session.execute(
        text(
            "SELECT refcount FROM ai_search_paths "
            "WHERE entity_type = :et AND path::text = :p AND value_type = CAST(:vt AS field_type)"
        ),
        {"et": entity_type, "p": path, "vt": value_type.value},
    ).fetchone()
    return row[0] if row else None


class _SplitBatchSession:
    """Split a two-row executemany so concurrent trigger writes interleave."""

    def __init__(self, session: Session, barrier: Barrier) -> None:
        self.session = session
        self.barrier = barrier

    def connection(self, *args, **kwargs):
        # The isolation-level guard inspects the underlying real session's connection.
        return self.session.connection(*args, **kwargs)

    def execute(self, statement, params=None, **kwargs):
        if isinstance(params, list) and len(params) == 2:
            self.session.execute(statement, [params[0]], **kwargs)
            try:
                self.barrier.wait(timeout=0.25)
            except BrokenBarrierError:
                pass
            return self.session.execute(statement, [params[1]], **kwargs)
        return self.session.execute(statement, params, **kwargs)


def test_concurrent_index_chunks_for_same_entity_type_do_not_deadlock():
    barrier = Barrier(2)
    errors: list[Exception] = []
    entity_ids = [uuid4() for _ in range(4)]

    def index(paths: tuple[str, str], ids: list[UUID]) -> None:
        config = MagicMock()
        config.entity_kind = EntityType.PROCESS
        indexer = Indexer(config=config, dry_run=False, force_index=True)
        fields = [
            (str(entity_id), ExtractedField(path=path, value="true", value_type=FieldType.BOOLEAN))
            for entity_id, path in zip(ids, paths)
        ]

        def determine_changes(*_args):
            indexer._entity_titles.update((entity_id, "process") for entity_id, _field in fields)
            return fields, [], 0, {}

        try:
            with Session(db.wrapped_database.engine) as session, session.begin():
                session.execute(text("SET LOCAL deadlock_timeout = '50ms'"))
                # Revalidation is neutralised here: this test's subject is advisory-lock
                # ordering, its config is a mock with no source table, and its entity ids
                # are synthetic — an existence recheck would legitimately drop all work.
                with (
                    patch.object(indexer, "_determine_changes", side_effect=determine_changes),
                    patch.object(
                        indexer,
                        "_revalidate_planned_writes",
                        side_effect=lambda batches, paths, baseline, sess: (batches, paths, []),
                    ),
                ):
                    indexer._process_chunk([MagicMock()], session=_SplitBatchSession(session, barrier))
        except Exception as error:
            errors.append(error)

    threads = [
        Thread(
            target=index,
            args=(("process.deadlock_a", "process.deadlock_b"), entity_ids[:2]),
        ),
        Thread(
            target=index,
            args=(("process.deadlock_b", "process.deadlock_a"), entity_ids[2:]),
        ),
    ]

    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        assert all(not thread.is_alive() for thread in threads)
        assert errors == []
    finally:
        with db.wrapped_database.engine.begin() as connection:
            connection.execute(delete(AiSearchIndex).where(AiSearchIndex.entity_id.in_(entity_ids)))


def test_remove_entity_from_index_waits_for_entity_type_write_lock():
    """A deleted-entity removal must not write while another transaction holds the entity-type lock."""
    barrier = Barrier(2, timeout=5)
    events: list[str] = []
    errors: list[Exception] = []
    entity_id = uuid4()

    def holder() -> None:
        try:
            with Session(db.wrapped_database.engine) as session, session.begin():
                acquire_search_index_write_lock(session, EntityType.PROCESS)
                barrier.wait()  # the lock is held once the remover is released
                time.sleep(0.5)
            events.append("holder_committed")
        except Exception as error:
            errors.append(error)

    def remover() -> None:
        try:
            barrier.wait()
            with Session(db.wrapped_database.engine) as session:
                _remove_entity_from_index(EntityType.PROCESS, str(entity_id), dry_run=False, session=session)
            events.append("remover_done")
        except Exception as error:
            errors.append(error)

    threads = [Thread(target=holder), Thread(target=remover)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert events == ["holder_committed", "remover_done"]


def test_indexer_scans_and_deletes_only_its_own_entity_type():
    """Hash scans and stale-path deletes must stay scoped to the indexer's own entity type.

    `ai_search_paths` rows are keyed by (entity_type, path, value_type), so the
    per-type advisory lock only serializes writes to the writer's own type's rows.
    A delete that also touches another type's rows would update those shared path
    rows without that type's lock.
    """
    entity_id = uuid4()
    foreign_path = "process.foreign_type"
    with db.wrapped_database.engine.begin() as conn:
        conn.execute(
            insert(AiSearchIndex),
            {
                "entity_id": entity_id,
                "entity_type": EntityType.PROCESS.value,
                "entity_title": "foreign",
                "path": Ltree(foreign_path),
                "value": "x",
                "value_type": FieldType.STRING,
                "content_hash": "deadbeef",
            },
        )
    try:
        config = MagicMock()
        config.entity_kind = EntityType.SCHEDULE
        indexer = Indexer(config=config, dry_run=False, force_index=False)
        with Session(db.wrapped_database.engine) as session, session.begin():
            hashes = indexer._get_all_existing_hashes([str(entity_id)], session)
            assert hashes[str(entity_id)] == {}

            indexer._execute_batched_deletes([(str(entity_id), Ltree(foreign_path))], session)
            remaining = session.execute(select(AiSearchIndex).where(AiSearchIndex.entity_id == entity_id)).all()
            assert len(remaining) == 1
    finally:
        with db.wrapped_database.engine.begin() as conn:
            conn.execute(delete(AiSearchIndex).where(AiSearchIndex.entity_id == entity_id))


# ---------------------------------------------------------------------------
# Stale-write revalidation under the entity-type lock (bulk-vs-hook race)
# ---------------------------------------------------------------------------


def _workflows_indexer() -> Indexer:
    config = MagicMock()
    config.entity_kind = EntityType.WORKFLOW
    config.pk_name = "workflow_id"
    config.table = WorkflowTable
    config.get_all_query.return_value = WorkflowTable.select()
    return Indexer(config=config, dry_run=False, force_index=False, chunk_size=10)


def _insert_workflow(description: str = "stale-write revalidation fixture") -> UUID:
    workflow_id = uuid4()
    with db.wrapped_database.engine.begin() as conn:
        conn.execute(
            insert(WorkflowTable).values(
                workflow_id=workflow_id,
                name=f"stale-write-race-{workflow_id}",
                target=Target.SYSTEM.value,
                description=description,
            )
        )
    return workflow_id


def _wf_record(
    entity_id: UUID, path: str, value: str, content_hash: str, value_type: FieldType = FieldType.STRING
) -> IndexableRecord:
    return IndexableRecord(
        entity_id=str(entity_id),
        entity_type=EntityType.WORKFLOW.value,
        entity_title="wf",
        path=Ltree(path),
        value=value,
        value_type=value_type,
        content_hash=content_hash,
        embedding=None,
    )


def _insert_index_row(
    entity_id: UUID, path: str, value: str, content_hash: str, value_type: FieldType = FieldType.STRING
) -> None:
    with db.wrapped_database.engine.begin() as conn:
        conn.execute(
            insert(AiSearchIndex).values(
                entity_id=entity_id,
                entity_type=EntityType.WORKFLOW.value,
                entity_title="wf",
                path=Ltree(path),
                value=value,
                value_type=value_type,
                content_hash=content_hash,
            )
        )


def _index_rows(entity_id: UUID) -> list:
    with db.wrapped_database.engine.connect() as conn:
        return conn.execute(
            select(AiSearchIndex.value, AiSearchIndex.content_hash).where(AiSearchIndex.entity_id == entity_id)
        ).all()


def _cleanup_index_race(entity_id: UUID, *, workflow: bool) -> None:
    with db.wrapped_database.engine.begin() as conn:
        conn.execute(delete(AiSearchIndex).where(AiSearchIndex.entity_id == entity_id))
        if workflow:
            conn.execute(delete(WorkflowTable).where(WorkflowTable.workflow_id == entity_id))


def test_bulk_write_does_not_overwrite_newer_indexed_value():
    """A bulk chunk that embedded a stale value must not clobber a newer hook-indexed row.

    The hook write commits while the chunk is preparing; the chunk then acquires the lock
    and must drop its prepared upsert instead of writing its older value back.
    """
    wf_id = _insert_workflow()
    path = "workflow.note"
    try:
        _insert_index_row(wf_id, path, "old", "h_old")

        # A single-entity (hook) reindex wins the race and commits first.
        with Session(db.wrapped_database.engine) as session, session.begin():
            acquire_search_index_write_lock(session, EntityType.WORKFLOW)
            session.execute(
                update(AiSearchIndex)
                .where(AiSearchIndex.entity_id == wf_id, AiSearchIndex.path == Ltree(path))
                .values(value="new", content_hash="h_new")
            )

        indexer = _workflows_indexer()
        stale_batch = [_wf_record(wf_id, path, "old", "h_old")]
        with (
            patch.object(
                indexer,
                "_determine_changes",
                return_value=([("eid", MagicMock())], [], 0, {str(wf_id): {path: "h_old"}}),
            ),
            patch.object(indexer, "_generate_upsert_batches", return_value=iter([stale_batch])),
        ):
            with Session(db.wrapped_database.engine) as session, session.begin():
                processed, _identical, dropped = indexer._process_chunk([MagicMock()], session=session)

        assert _index_rows(wf_id) == [("new", "h_new")]
        assert processed == 0
        assert dropped == [str(wf_id)]
    finally:
        _cleanup_index_race(wf_id, workflow=True)


def test_bulk_write_does_not_resurrect_deleted_entity():
    """An entity deleted after the chunk read it must not get index rows written for it."""
    ghost_id = uuid4()  # never present in the source table: deleted after the chunk read it
    path = "workflow.note"
    try:
        indexer = _workflows_indexer()
        prepared = [_wf_record(ghost_id, path, "value", "h_prepared")]
        with (
            patch.object(indexer, "_determine_changes", return_value=([("eid", MagicMock())], [], 0, {})),
            patch.object(indexer, "_generate_upsert_batches", return_value=iter([prepared])),
        ):
            with Session(db.wrapped_database.engine) as session, session.begin():
                processed, _identical, dropped = indexer._process_chunk([MagicMock()], session=session)

        assert _index_rows(ghost_id) == []
        assert processed == 0
        assert dropped == [str(ghost_id)]
    finally:
        _cleanup_index_race(ghost_id, workflow=False)


def test_stale_delete_cancelled_by_concurrent_reindex():
    """A planned stale-path delete must not remove a row a concurrent reindex just refreshed."""
    wf_id = _insert_workflow()
    path = "workflow.stale"
    try:
        _insert_index_row(wf_id, path, "old", "h_base")

        # Concurrent reindex refreshes the path the chunk planned to delete.
        with Session(db.wrapped_database.engine) as session, session.begin():
            acquire_search_index_write_lock(session, EntityType.WORKFLOW)
            session.execute(
                update(AiSearchIndex)
                .where(AiSearchIndex.entity_id == wf_id, AiSearchIndex.path == Ltree(path))
                .values(value="fresh", content_hash="h_fresh")
            )

        indexer = _workflows_indexer()
        planned_delete = [(str(wf_id), Ltree(path))]
        with patch.object(
            indexer,
            "_determine_changes",
            return_value=([], planned_delete, 0, {str(wf_id): {path: "h_base"}}),
        ):
            with Session(db.wrapped_database.engine) as session, session.begin():
                _processed, _identical, dropped = indexer._process_chunk([MagicMock()], session=session)

        assert _index_rows(wf_id) == [("fresh", "h_fresh")]
        assert dropped == []
    finally:
        _cleanup_index_race(wf_id, workflow=True)


def test_insert_creates_path_with_refcount_one():
    _add_index_row("subscription.node.name")
    assert _refcount("subscription.node.name", FieldType.STRING) == 1


def test_second_entity_same_tuple_increments_refcount():
    _add_index_row("subscription.node.name")
    _add_index_row("subscription.node.name")
    assert _refcount("subscription.node.name", FieldType.STRING) == 2


def test_delete_one_of_two_keeps_row_at_one():
    first = _add_index_row("subscription.node.name")
    _add_index_row("subscription.node.name")
    db.session.execute(delete(AiSearchIndex).where(AiSearchIndex.entity_id == first))
    db.session.flush()
    assert _refcount("subscription.node.name", FieldType.STRING) == 1


def test_delete_last_removes_row():
    eid = _add_index_row("subscription.node.name")
    db.session.execute(delete(AiSearchIndex).where(AiSearchIndex.entity_id == eid))
    db.session.flush()
    assert _refcount("subscription.node.name", FieldType.STRING) is None


def test_update_value_type_moves_refcount_between_tuples():
    eid = _add_index_row("subscription.node.enabled", value_type=FieldType.STRING)
    db.session.execute(update(AiSearchIndex).where(AiSearchIndex.entity_id == eid).values(value_type=FieldType.BOOLEAN))
    db.session.flush()
    assert _refcount("subscription.node.enabled", FieldType.STRING) is None
    assert _refcount("subscription.node.enabled", FieldType.BOOLEAN) == 1


def test_reindex_same_tuple_is_noop():
    eid = _add_index_row("subscription.node.name", value="old")
    db.session.execute(update(AiSearchIndex).where(AiSearchIndex.entity_id == eid).values(value="new"))
    db.session.flush()
    assert _refcount("subscription.node.name", FieldType.STRING) == 1


def test_distinct_tuples_tracked_separately():
    _add_index_row("subscription.node.name", entity_type="SUBSCRIPTION")
    _add_index_row("subscription.node.name", entity_type="PRODUCT")
    assert _refcount("subscription.node.name", FieldType.STRING, "SUBSCRIPTION") == 1
    assert _refcount("subscription.node.name", FieldType.STRING, "PRODUCT") == 1


def _all_paths_rows() -> set[tuple]:
    """Return the full ai_search_paths contents as a comparable set."""
    rows = db.session.execute(
        text("SELECT entity_type, path::text, value_type::text, refcount FROM ai_search_paths")
    ).fetchall()
    return {tuple(r) for r in rows}


def _expected_paths_rows() -> set[tuple]:
    """Recompute the expected distinct-paths contents directly from ai_search_index."""
    rows = db.session.execute(
        text(
            "SELECT entity_type, path::text, value_type::text, count(*) "
            "FROM ai_search_index GROUP BY entity_type, path, value_type"
        )
    ).fetchall()
    return {tuple(r) for r in rows}


def test_rebuild_reconstructs_exact_table_after_drift():
    _add_index_row("subscription.node.name")
    _add_index_row("subscription.node.name")
    _add_index_row("subscription.node.speed", value_type=FieldType.INTEGER)

    # Corrupt the derived table: wrong refcount, a spurious row, and a missing row.
    db.session.execute(text("UPDATE ai_search_paths SET refcount = 99 WHERE path::text = 'subscription.node.name'"))
    db.session.execute(
        text(
            "INSERT INTO ai_search_paths (entity_type, path, value_type, refcount) "
            "VALUES ('SUBSCRIPTION', 'bogus.path'::ltree, CAST('string' AS field_type), 5)"
        )
    )
    db.session.execute(text("DELETE FROM ai_search_paths WHERE path::text = 'subscription.node.speed'"))
    db.session.flush()

    rebuild_search_paths()

    assert _all_paths_rows() == _expected_paths_rows()


def test_rebuild_on_empty_index_yields_empty_table():
    _add_index_row("subscription.node.name")
    db.session.execute(delete(AiSearchIndex))
    db.session.flush()
    rebuild_search_paths()
    assert _all_paths_rows() == set()


def test_build_paths_query_returns_leaves_and_components_from_trigger_table():
    # Two entities share the leaf path; a nested path contributes a component.
    _add_index_row("subscription.node.name", entity_id=uuid4())
    _add_index_row("subscription.node.name", entity_id=uuid4())
    _add_index_row("subscription.node.speed", value_type=FieldType.INTEGER)
    # A different entity_type must not leak into SUBSCRIPTION results.
    _add_index_row("product.other.field", entity_type="PRODUCT")

    stmt = build_paths_query(EntityType.SUBSCRIPTION)
    rows = db.session.execute(stmt).all()
    leaves, components = process_path_rows(rows)

    leaf_names = {leaf.name for leaf in leaves}
    component_names = {c.name for c in components}
    assert leaf_names == {"name", "speed"}
    assert component_names == {"node"}
    assert "field" not in leaf_names  # PRODUCT row excluded by the entity_type filter


@pytest.mark.parametrize(
    ("prefix", "expected_leaves"),
    [
        pytest.param("subscription.node", {"name"}, id="prefix-matches-node"),
        pytest.param("subscription.iface", set(), id="prefix-matches-nothing"),
    ],
)
def test_build_paths_query_prefix_filter(prefix, expected_leaves):
    _add_index_row("subscription.node.name")
    stmt = build_paths_query(EntityType.SUBSCRIPTION, prefix=prefix)
    leaves, _ = process_path_rows(db.session.execute(stmt).all())
    assert {leaf.name for leaf in leaves} == expected_leaves


def test_build_paths_query_orders_by_similarity_to_q():
    _add_index_row("subscription.node.description")
    _add_index_row("subscription.node.name")

    stmt = build_paths_query(EntityType.SUBSCRIPTION, q="name")
    rows = db.session.execute(stmt).all()
    paths = [str(row[0]) for row in rows]

    assert paths.index("subscription.node.name") < paths.index("subscription.node.description")


def test_build_paths_query_does_not_apply_a_limit_itself():
    _add_index_row("subscription.node.name")
    _add_index_row("subscription.node.speed", value_type=FieldType.INTEGER)
    _add_index_row("subscription.node.enabled", value_type=FieldType.BOOLEAN)

    stmt = build_paths_query(EntityType.SUBSCRIPTION).limit(2)
    rows = db.session.execute(stmt).all()

    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Round 2 review regressions: source-fresh planning, force repair, retry
# recovery, soft-delete existence, string-pk binding (real PostgreSQL)
# ---------------------------------------------------------------------------

workflow_config = ENTITY_CONFIG_REGISTRY[EntityType.WORKFLOW]


def _no_embedding_api():
    """Patch the embedding API so prepared records get deterministic vectors."""
    return patch(
        "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
        side_effect=lambda texts, dry_run: [[0.0] * 1536 for _ in texts],
    )


def _fresh_workflow_description(wf_id: UUID) -> ExtractedField:
    config = ENTITY_CONFIG_REGISTRY[EntityType.WORKFLOW]
    with Session(db.wrapped_database.engine) as session:
        wf = session.get(WorkflowTable, wf_id)
        fields = config.traverser.get_fields(wf, pk_name=config.pk_name, root_name=config.root_name)
    return next(f for f in fields if str(f.path).endswith(".description"))


def _index_row(entity_id: UUID, path: str) -> tuple | None:
    with db.wrapped_database.engine.connect() as conn:
        return conn.execute(
            select(AiSearchIndex.value, AiSearchIndex.content_hash).where(
                AiSearchIndex.entity_id == entity_id, AiSearchIndex.path == Ltree(path)
            )
        ).first()


def test_streamed_source_cannot_clobber_newer_hook_write() -> None:
    """A chunk handed a stale stream snapshot replans from the fresh source instead.

    The stream read (T0) and the hook write interleave such that the stored baseline
    already holds the newer value: hash-only revalidation would admit the stale plan
    (current == baseline), so planning must come from a fresh source read.
    """
    wf_id = _insert_workflow(description="new-value")
    try:
        indexer = Indexer(config=workflow_config, dry_run=False, force_index=False, chunk_size=10)

        # Hook write commits first: the index now holds the newer state of every field.
        with _no_embedding_api():
            with Session(db.wrapped_database.engine) as session, session.begin():
                processed, _identical, _dropped = indexer._process_chunk([session.get(WorkflowTable, wf_id)], session)
        assert processed >= 1

        # The bulk stream snapshot was read BEFORE that write: stale description value.
        with db.wrapped_database.engine.connect() as conn:
            name = conn.execute(select(WorkflowTable.name).where(WorkflowTable.workflow_id == wf_id)).scalar_one()
        stale_stream_row = WorkflowTable(
            workflow_id=wf_id, name=name, target=Target.SYSTEM.value, description="old-value"
        )

        with _no_embedding_api():
            with Session(db.wrapped_database.engine) as session, session.begin():
                processed, identical, dropped = indexer._process_chunk([stale_stream_row], session)

        assert processed == 0
        assert identical >= 1
        assert dropped == []
        desc_row = _index_row(wf_id, str(_fresh_workflow_description(wf_id).path))
        assert desc_row is not None
        assert desc_row[0] == "new-value"  # the stale stream value never reached the index
    finally:
        _cleanup_index_race(wf_id, workflow=True)


def test_force_reindex_repairs_drifted_row() -> None:
    """Force mode must repair a row whose stored hash drifted, not drop it as a competing write."""
    wf_id = _insert_workflow()
    try:
        desc = _fresh_workflow_description(wf_id)
        path = str(desc.path)
        fresh_hash = Indexer._compute_content_hash(desc.path, desc.value, desc.value_type, "wf")
        _insert_index_row(wf_id, path, "drifted", "drift", value_type=desc.value_type)

        indexer = Indexer(config=workflow_config, dry_run=False, force_index=True, chunk_size=10)
        fresh_record = _wf_record(wf_id, path, desc.value, fresh_hash, value_type=desc.value_type)
        with patch.object(indexer, "_generate_upsert_batches", return_value=iter([[fresh_record]])):
            with Session(db.wrapped_database.engine) as session, session.begin():
                with _no_embedding_api():
                    processed, _identical, dropped = indexer._process_chunk(
                        [session.get(WorkflowTable, wf_id)], session
                    )

        assert dropped == []
        assert processed == 1
        assert _index_row(wf_id, path) == (desc.value, fresh_hash)
    finally:
        _cleanup_index_race(wf_id, workflow=True)


@pytest.mark.usefixtures("committing_db_session")
def test_run_retry_recovers_dropped_entity_with_real_session() -> None:
    """run()'s retry pass reloads and rewrites inside a real transaction.

    The main pass plans from a phantom baseline and embeds a stale value; revalidation
    drops it. The retry must reload the entity and write the fresh value — without
    tripping SQLAlchemy's "transaction is already begun". Everything runs on the app's
    real engine-bound scoped sessions: setup commits, run() commits independently,
    and the opt-in fixture explicitly removes committed test data.
    """
    wf_id = uuid4()
    db.session.add(
        WorkflowTable(
            workflow_id=wf_id,
            name=f"stale-write-race-{wf_id}",
            target=Target.SYSTEM.value,
            description="retry fixture",
        )
    )
    db.session.commit()

    wf = db.session.get(WorkflowTable, wf_id)
    fields = workflow_config.traverser.get_fields(
        wf, pk_name=workflow_config.pk_name, root_name=workflow_config.root_name
    )
    desc = next(f for f in fields if str(f.path).endswith(".description"))
    path = str(desc.path)
    fresh_hash = Indexer._compute_content_hash(
        desc.path, desc.value, desc.value_type, workflow_config.get_title_from_fields(fields)
    )
    db.session.add(
        AiSearchIndex(
            entity_type=EntityType.WORKFLOW.value,
            entity_id=wf_id,
            entity_title="wf",
            path=Ltree(path),
            value="stored-old",
            value_type=desc.value_type,
            content_hash="h_stored_old",
        )
    )
    db.session.commit()

    indexer = Indexer(config=workflow_config, dry_run=False, force_index=False, chunk_size=10)
    stale_record = _wf_record(wf_id, path, "old-value", "h_stale_prepared", value_type=desc.value_type)
    fresh_record = _wf_record(wf_id, path, desc.value, fresh_hash, value_type=desc.value_type)

    real_hashes = indexer._get_all_existing_hashes
    hash_calls: list[int] = []

    def baseline_then_reals(entity_ids, session=None):
        hash_calls.append(1)
        if len(hash_calls) == 1:
            # Simulate the chunk having read its baseline before a newer write landed.
            return {str(wf_id): {path: "h_phantom"}}
        return real_hashes(entity_ids, session)

    with (
        patch.object(indexer, "_get_all_existing_hashes", side_effect=baseline_then_reals),
        patch.object(indexer, "_generate_upsert_batches", side_effect=[iter([[stale_record]]), iter([[fresh_record]])]),
    ):
        result = indexer.run([wf])

    assert result == 1
    assert _index_row(wf_id, path) == (desc.value, fresh_hash)


def test_soft_deleted_workflow_does_not_resurrect_rows() -> None:
    """A workflow soft-deleted after the chunk read it must not get index rows written."""
    wf_id = _insert_workflow()
    path = "workflow.note"
    try:
        with db.wrapped_database.engine.begin() as conn:
            conn.execute(update(WorkflowTable).where(WorkflowTable.workflow_id == wf_id).values(deleted_at=nowtz()))

        indexer = _workflows_indexer()
        prepared = [_wf_record(wf_id, path, "value", "h_prepared")]
        with (
            patch.object(indexer, "_determine_changes", return_value=([("eid", MagicMock())], [], 0, {})),
            patch.object(indexer, "_generate_upsert_batches", return_value=iter([prepared])),
        ):
            with Session(db.wrapped_database.engine) as session, session.begin():
                processed, _identical, dropped = indexer._process_chunk([MagicMock()], session=session)

        assert _index_rows(wf_id) == []
        assert processed == 0
        assert dropped == [str(wf_id)]
    finally:
        _cleanup_index_race(wf_id, workflow=True)


def test_schedule_queries_bind_string_ids() -> None:
    """Schedule ids live in a String(512) column: UUID coercion breaks against PostgreSQL."""
    config = ENTITY_CONFIG_REGISTRY[EntityType.SCHEDULE]
    indexer = Indexer(config=config, dry_run=False, force_index=False, chunk_size=10)
    schedule_id = str(uuid4())

    with Session(db.wrapped_database.engine) as session:
        assert indexer._fetch_alive_ids([schedule_id], session) == set()
        assert indexer._load_source_entities([schedule_id], session) == []


def test_retry_dropped_in_borrowed_transaction_is_skipped_with_warning() -> None:
    """A borrowed (caller-owned) transaction may still hold the advisory lock: the retry is skipped.

    Running the retry would embed while the caller's transaction-scoped lock is held,
    blocking every same-type hook. The dropped ids must be surfaced in a warning and
    the stored rows left untouched for the next scheduled reindex.
    """
    wf_id = _insert_workflow()
    try:
        desc = _fresh_workflow_description(wf_id)
        path = str(desc.path)
        _insert_index_row(wf_id, path, "stored-old", "h_stored_old", value_type=desc.value_type)

        indexer = Indexer(config=workflow_config, dry_run=False, force_index=False, chunk_size=10)
        indexer._dropped_entity_ids = {str(wf_id)}
        indexer.logger = MagicMock()

        with Session(db.wrapped_database.engine) as session, session.begin():
            processed, _identical = indexer._retry_dropped(session)

        assert (processed, _identical) == (0, 0)
        assert not indexer._dropped_entity_ids
        warning = next(c for c in indexer.logger.warning.call_args_list if "retry" in str(c.args[0]).lower())
        assert warning.kwargs["dropped_entity_ids"] == [str(wf_id)]
        assert _index_row(wf_id, path) == ("stored-old", "h_stored_old")
    finally:
        _cleanup_index_race(wf_id, workflow=True)


def test_retry_dropped_begins_and_commits_when_it_owns_the_transaction() -> None:
    """With no transaction active, the retry owns its transaction: begins, commits, work persists."""
    wf_id = _insert_workflow()
    try:
        desc = _fresh_workflow_description(wf_id)
        path = str(desc.path)
        fresh_hash = Indexer._compute_content_hash(desc.path, desc.value, desc.value_type, "wf")
        _insert_index_row(wf_id, path, "stored-old", "h_stored_old", value_type=desc.value_type)

        indexer = Indexer(config=workflow_config, dry_run=False, force_index=False, chunk_size=10)
        fresh_record = _wf_record(wf_id, path, desc.value, fresh_hash, value_type=desc.value_type)
        indexer._dropped_entity_ids = {str(wf_id)}

        with Session(db.wrapped_database.engine) as session:
            with patch.object(indexer, "_generate_upsert_batches", return_value=iter([[fresh_record]])):
                processed, _identical = indexer._retry_dropped(session)

        assert processed == 1
        assert _index_row(wf_id, path) == (desc.value, fresh_hash)
    finally:
        _cleanup_index_race(wf_id, workflow=True)


def test_subscription_planning_evicts_run_cached_model(generic_subscription_1, db_session) -> None:
    """A subscription cached earlier in the run must be rebuilt fresh when its chunk is planned."""
    sub_id = UUID(generic_subscription_1)
    indexer = Indexer(
        config=ENTITY_CONFIG_REGISTRY[EntityType.SUBSCRIPTION], dry_run=False, force_index=False, chunk_size=10
    )
    with cache_subscription_models():
        cached = SubscriptionModel.from_subscription(sub_id)  # what an earlier chunk's computed_field would do
        stale_description = cached.description
        fresh_description = f"hook-updated-{sub_id}"

        # A hook-style update lands before the bulk reaches this subscription's chunk.
        db.session.execute(
            update(SubscriptionTable)
            .where(SubscriptionTable.subscription_id == sub_id)
            .values(description=fresh_description)
        )
        db.session.flush()

        row = db.session.get(SubscriptionTable, sub_id)
        fields_to_upsert, _deletes, _identical, _baseline = indexer._determine_changes([row], session=db.session)

    planned_subscription_description = {
        field.value for _eid, field in fields_to_upsert if str(field.path) == "subscription.description"
    }
    assert planned_subscription_description == {fresh_description}
    assert stale_description not in planned_subscription_description


@pytest.mark.usefixtures("committing_db_session")
def test_run_rejects_lazy_entities_stream_from_its_own_session() -> None:
    """A lazy entities iterable querying db.session inside run() autobegins run()'s write transaction.

    run() would silently join that transaction, never commit it, and roll every write
    back when the scope exits — while reporting the records as processed. run() must
    raise instead. The shipped task path is safe for a different reason than
    materialization: tasks.py runs its stream query (peekable over an executed
    result) BEFORE entering run()'s write scope, so it binds to the outer session.
    """
    wf_id = _insert_workflow("lazy-stream contract")
    try:
        _insert_index_row(wf_id, "workflow.description", "stale-old", "h0")

        def lazy_stream():
            # db.session resolves at consumption time, inside run()'s database_scope:
            # this SELECT autobegins the very session run() intends to own.
            yield from db.session.scalars(select(WorkflowTable).where(WorkflowTable.workflow_id == wf_id))

        indexer = _workflows_indexer()
        with pytest.raises(RuntimeError, match="materialize"):
            indexer.run(lazy_stream())

        assert _index_row(wf_id, "workflow.description") == ("stale-old", "h0")
    finally:
        _cleanup_index_race(wf_id, workflow=True)


def test_process_chunk_rejects_unflushed_source_edit_on_planning_session() -> None:
    """The source-fresh reload (populate_existing) would silently discard a pending edit.

    A caller that edits a planned row on the planning session without flushing must be
    rejected before the reload touches its objects, not have its change reverted.
    """
    wf_id = _insert_workflow("unflushed-edit guard")
    try:
        with Session(db.wrapped_database.engine) as caller:
            wf = caller.get(WorkflowTable, wf_id)
            wf.description = "pending-hook-edit"

            indexer = Indexer(
                config=ENTITY_CONFIG_REGISTRY[EntityType.WORKFLOW], dry_run=False, force_index=False, chunk_size=10
            )
            with caller.no_autoflush:
                with pytest.raises(RuntimeError, match="flush"):
                    indexer._process_chunk([wf], session=caller)

            assert wf.description == "pending-hook-edit"  # edit survived the refused planning pass
            assert wf in caller.dirty
    finally:
        _cleanup_index_race(wf_id, workflow=True)  # _insert_workflow committed on its own connection


@pytest.mark.timeout(30)
@pytest.mark.parametrize("edit_root", [True, False])
def test_process_chunk_rejects_pending_changes_before_autoflushing_them(edit_root: bool) -> None:
    """The pending-changes guard must run before the first query, not after an autoflush.

    With the application's default autoflush, a baseline SELECT would flush the caller's
    pending UPDATE — emptying session.dirty, defeating the guard, and letting the pass
    proceed (and dry-run issue DML). Pending edits to rows the plan never touches are
    rejected too: the source-fresh reload eager-loads and reverts related rows.
    """
    wf_id = _insert_workflow("pending-autoflush guard")
    sibling_id = _insert_workflow("pending-sibling")
    try:
        with Session(db.wrapped_database.engine) as caller, _no_embedding_api():
            indexer = Indexer(
                config=ENTITY_CONFIG_REGISTRY[EntityType.WORKFLOW], dry_run=False, force_index=False, chunk_size=10
            )
            wf = caller.get(WorkflowTable, wf_id)
            sibling = caller.get(WorkflowTable, sibling_id)
            edited = wf if edit_root else sibling
            edited.description = "pending-edit"

            with pytest.raises(RuntimeError, match="flush"):
                indexer._process_chunk([wf], session=caller)

            assert edited.description == "pending-edit"
            assert edited in caller.dirty  # the UPDATE never reached the connection
    finally:
        _cleanup_index_race(wf_id, workflow=True)
        _cleanup_index_race(sibling_id, workflow=True)


@pytest.mark.timeout(30)
@pytest.mark.parametrize("driver_autocommit", [False, True])
def test_process_chunk_rejects_autocommit_session(driver_autocommit: bool) -> None:
    """A DBAPI-autocommit connection cannot hold the transaction-scoped advisory lock.

    get_isolation_level() never reports AUTOCOMMIT (it answers READ COMMITTED), so the
    READ COMMITTED guard cannot catch it: pg_advisory_xact_lock is released the moment
    its statement returns, and the revalidation races hooks with no serialization while
    every write commits on its own. Check the DBAPI mode independently, including when
    autocommit is enabled directly on the driver rather than through execution options.
    """
    wf_id = _insert_workflow("autocommit guard")
    try:
        autocommit_conn = db.wrapped_database.engine.connect()
        dbapi_connection = autocommit_conn.connection.dbapi_connection
        original_autocommit = dbapi_connection.autocommit
        try:
            if driver_autocommit:
                autocommit_conn.connection.dbapi_connection.autocommit = True
            else:
                autocommit_conn = autocommit_conn.execution_options(isolation_level="AUTOCOMMIT")
            with Session(autocommit_conn) as session:
                wf = session.get(WorkflowTable, wf_id)
                indexer = Indexer(config=workflow_config, dry_run=False, force_index=False, chunk_size=10)
                assert autocommit_conn.get_isolation_level() == "READ COMMITTED"
                with _no_embedding_api(), pytest.raises(RuntimeError, match="advisory lock"):
                    indexer._process_chunk([wf], session=session)
                assert _index_rows(wf_id) == []  # nothing was written before the refusal
        finally:
            try:
                if driver_autocommit:
                    # Pool rollback-on-return cannot undo direct driver configuration.
                    dbapi_connection.autocommit = original_autocommit
            finally:
                autocommit_conn.close()
        assert dbapi_connection.autocommit is original_autocommit
    finally:
        _cleanup_index_race(wf_id, workflow=True)


@pytest.mark.timeout(30)
@pytest.mark.parametrize("force_index", [False, True])
def test_dry_run_never_autoflushes_pending_changes(force_index: bool) -> None:
    """Dry-run must preserve pending edits without emitting DML, even when force indexing."""
    wf_id = _insert_workflow("dry-run pending edit")
    try:
        with Session(db.wrapped_database.engine) as session:
            wf = session.get(WorkflowTable, wf_id)
            wf.description = "pending-edit"
            flushed: list[bool] = []
            event.listen(session, "before_flush", lambda *_: flushed.append(True))
            indexer = Indexer(config=workflow_config, dry_run=True, force_index=force_index, chunk_size=10)

            with _no_embedding_api():
                indexer._process_chunk([wf], session=session)

            assert flushed == []
            assert wf.description == "pending-edit"
            assert wf in session.dirty
            assert _index_rows(wf_id) == []
    finally:
        _cleanup_index_race(wf_id, workflow=True)


@pytest.mark.timeout(30)
def test_planning_preserves_pending_edits_to_eager_loaded_related_rows() -> None:
    """Refreshing a schedule also refreshes its workflow: pending child edits must survive refusal."""
    wf_id = _insert_workflow("related-edit guard")
    schedule_id = str(uuid4())
    try:
        with db.wrapped_database.engine.begin() as conn:
            conn.execute(insert(APSchedulerJobStoreModel).values(id=schedule_id, job_state=b"unused"))
            conn.execute(insert(WorkflowApschedulerJob).values(workflow_id=wf_id, schedule_id=schedule_id))
        with Session(db.wrapped_database.engine) as session:
            config = ENTITY_CONFIG_REGISTRY[EntityType.SCHEDULE]
            schedule = session.scalars(config.get_all_query(schedule_id)).one()
            workflow = schedule.workflow
            workflow.description = "pending-related-edit"
            indexer = Indexer(config=config, dry_run=False, force_index=False, chunk_size=10)

            with (
                session.no_autoflush,
                patch("orchestrator.core.schedules.scheduler.get_scheduler_task", return_value=None),
                pytest.raises(RuntimeError, match="flush"),
            ):
                indexer._determine_changes([schedule], session=session)

            assert workflow.description == "pending-related-edit"
            assert workflow in session.dirty
    finally:
        with db.wrapped_database.engine.begin() as conn:
            conn.execute(delete(APSchedulerJobStoreModel).where(APSchedulerJobStoreModel.id == schedule_id))
        _cleanup_index_race(wf_id, workflow=True)


def test_process_chunk_rejects_repeatable_read_session() -> None:
    """Under REPEATABLE READ the under-lock recheck sees the pre-plan snapshot: refuse to write.

    A concurrent delete (or newer hook write) committed after the baseline read would be
    invisible to the recheck, so stale upserts and resurrected entities would pass —
    without any serialization error. The application never pins the isolation level, so
    a database or role default can silently set REPEATABLE READ even through run().
    """
    wf_id = _insert_workflow("rr guard")
    try:
        conn = db.wrapped_database.engine.connect().execution_options(isolation_level="REPEATABLE READ")
        try:
            with Session(conn) as session:
                wf = session.get(WorkflowTable, wf_id)
                indexer = Indexer(config=workflow_config, dry_run=False, force_index=False, chunk_size=10)
                with pytest.raises(RuntimeError, match="READ COMMITTED"):
                    indexer._process_chunk([wf], session=session)
        finally:
            conn.close()
    finally:
        _cleanup_index_race(wf_id, workflow=True)


@pytest.mark.timeout(30)
@pytest.mark.parametrize("savepoint", [False, True])
def test_run_rejects_external_connection_transaction_without_touching_caller_work(savepoint: bool) -> None:
    """Refusal must precede planning and leave the caller's transaction/savepoint and edits intact."""
    wf_id = _insert_workflow("external-owner")
    try:
        database = db.wrapped_database
        real_scope = database.database_scope
        indexer = _workflows_indexer()
        with database.engine.connect() as connection, connection.begin() as outer:
            with connection.begin_nested() if savepoint else nullcontext() as nested:
                connection.execute(
                    update(WorkflowTable).where(WorkflowTable.workflow_id == wf_id).values(description="caller-pending")
                )
                statements: list[str] = []
                event.listen(connection, "before_cursor_execute", lambda _c, _s, sql, *_: statements.append(sql))

                with (
                    patch.object(database, "database_scope", side_effect=lambda: real_scope(bind=connection)),
                    patch.object(indexer, "_process_chunk", return_value=(0, 0, [])) as process,
                    pytest.raises(RuntimeError, match="externally.*transaction"),
                ):
                    indexer.run([WorkflowTable(workflow_id=wf_id)])

                assert statements == []  # not even a baseline read or BEGIN/savepoint
                process.assert_not_called()
                assert outer.is_active
                assert nested is None or nested.is_active
                assert (
                    connection.scalar(select(WorkflowTable.description).where(WorkflowTable.workflow_id == wf_id))
                    == "caller-pending"
                )
                with database.engine.connect() as reader:
                    assert (
                        reader.scalar(select(WorkflowTable.description).where(WorkflowTable.workflow_id == wf_id))
                        == "external-owner"
                    )
            outer.rollback()  # only the owner may discard its pending work
    finally:
        _cleanup_index_race(wf_id, workflow=True)


@pytest.mark.timeout(30)
def test_retry_skips_external_connection_transaction_even_when_session_is_idle() -> None:
    """An idle Session can hide an external transaction that still holds the first pass's lock."""
    indexer = _workflows_indexer()
    entity_id = str(uuid4())
    indexer._dropped_entity_ids = {entity_id}
    indexer.logger = MagicMock()
    with db.wrapped_database.engine.connect() as connection, connection.begin() as outer:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('orchestrator.search.indexer'), hashtext(:entity_type))"),
            {"entity_type": EntityType.WORKFLOW.value},
        )
        with Session(connection) as session:
            assert not session.in_transaction()
            with patch.object(indexer, "_load_source_entities", return_value=[]) as reload:
                assert indexer._retry_dropped(session) == (0, 0)
            reload.assert_not_called()
            assert not session.in_transaction()
            assert outer.is_active

        assert not indexer._dropped_entity_ids
        assert indexer.logger.warning.call_args.kwargs["reason"] == "external_connection_transaction"
        assert indexer.logger.warning.call_args.kwargs["dropped_entity_ids"] == [entity_id]
        with db.wrapped_database.engine.begin() as reader:
            assert (
                reader.scalar(
                    text(
                        "SELECT pg_try_advisory_xact_lock(hashtext('orchestrator.search.indexer'), hashtext('WORKFLOW'))"
                    )
                )
                is False
            )  # the indexer did not release the caller's lock


@pytest.mark.timeout(30)
@pytest.mark.parametrize("connection_bound", [False, True])
def test_strict_owned_transaction_commits_and_releases_the_lock(connection_bound: bool) -> None:
    """Engine and idle-Connection bindings must own real commits, not merely Session state."""
    wf_id = _insert_workflow("owned-before")
    engine = db.wrapped_database.engine
    try:
        with engine.connect() if connection_bound else nullcontext(engine) as bind:
            with Session(bind) as session:
                with _maybe_begin(session, allow_borrow=False):
                    acquire_search_index_write_lock(session, EntityType.WORKFLOW)
                    session.execute(
                        update(WorkflowTable)
                        .where(WorkflowTable.workflow_id == wf_id)
                        .values(description="owned-after")
                    )
                assert not session.in_transaction()
                with engine.begin() as reader:
                    assert (
                        reader.scalar(select(WorkflowTable.description).where(WorkflowTable.workflow_id == wf_id))
                        == "owned-after"
                    )
                    assert (
                        reader.scalar(
                            text(
                                "SELECT pg_try_advisory_xact_lock("
                                "hashtext('orchestrator.search.indexer'), hashtext('WORKFLOW'))"
                            )
                        )
                        is True
                    )
    finally:
        _cleanup_index_race(wf_id, workflow=True)


@pytest.mark.timeout(30)
@pytest.mark.usefixtures("committing_db_session")
def test_run_releases_lock_between_chunks_and_retry_embeddings() -> None:
    """Every embedding, including both retry partitions, runs outside earlier chunks' locks."""
    engine = db.wrapped_database.engine
    entity_ids = [_insert_workflow(f"initial-{i}") for i in range(2)]
    rows = [db.session.get(WorkflowTable, entity_id) for entity_id in entity_ids]
    indexer = Indexer(config=workflow_config, dry_run=False, force_index=False, chunk_size=1)
    embedding_calls: list[list[str]] = []

    def embed(texts, dry_run):
        assert not dry_run
        with engine.begin() as hook:
            assert (
                hook.scalar(
                    text(
                        "SELECT pg_try_advisory_xact_lock(hashtext('orchestrator.search.indexer'), hashtext('WORKFLOW'))"
                    )
                )
                is True
            ), "a previous chunk/partition retained its advisory lock during embedding"
            if len(embedding_calls) < 2:
                # The hook commits a source update and newer index value after the bulk
                # prepared this entity. Revalidation must drop it and trigger one retry.
                entity_id = entity_ids[len(embedding_calls)]
                fresh_value = f"hook-updated-{entity_id}"
                hook.execute(
                    update(WorkflowTable).where(WorkflowTable.workflow_id == entity_id).values(description=fresh_value)
                )
                hook.execute(
                    insert(AiSearchIndex).values(
                        **_wf_record(entity_id, "workflow.description", fresh_value, f"hook-hash-{entity_id}")
                    )
                )
        embedding_calls.append(texts)
        return [[0.0] * 1536 for _ in texts]

    with (
        patch(
            "orchestrator.core.search.core.embedding.EmbeddingIndexer.get_embeddings_from_api_batch",
            side_effect=embed,
        ),
        patch("orchestrator.core.search.indexing.indexer.llm_settings.EMBEDDING_MAX_BATCH_SIZE", 100),
    ):
        assert indexer.run(rows) > 0

    assert len(embedding_calls) == 4  # two first-pass chunks and two bounded retry partitions
    assert not indexer._dropped_entity_ids
    for entity_id in entity_ids:
        assert _index_row(entity_id, "workflow.description")[0] == f"hook-updated-{entity_id}"
