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

"""Freshness across actual computed fields, SQLAlchemy state and production tasks."""

import json
from contextlib import contextmanager
from contextvars import Context
from uuid import uuid4

import pytest
from pydantic import computed_field
from sqlalchemy import event, select, text, update
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from sqlalchemy_utils.types.ltree import Ltree

from orchestrator.core.db import db
from orchestrator.core.db.database import SESSION_ARGUMENTS
from orchestrator.core.db.models import AiSearchIndex, ProductTable, SubscriptionTable, WorkflowTable
from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY, SubscriptionModel
from orchestrator.core.domain.context_cache import (
    cache_subscription_models,
    get_from_cache,
    no_subscription_model_cache,
)
from orchestrator.core.search.core.embedding import EmbeddingIndexer
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.indexing.indexer import Indexer
from orchestrator.core.search.indexing.registry import ENTITY_CONFIG_REGISTRY, EntityConfig
from orchestrator.core.search.indexing.tasks import _remove_entity_from_index, run_indexing_for_entity
from orchestrator.core.utils.datetime import nowtz

pytestmark = [pytest.mark.search, pytest.mark.timeout(30)]


@pytest.fixture
def embedding_api(monkeypatch):
    """Keep real batching/tokenization but replace only the external network boundary."""

    def embed(texts, dry_run):
        return [[] for _ in texts]

    monkeypatch.setattr(EmbeddingIndexer, "get_embeddings_from_api_batch", embed)
    return embed


@pytest.fixture
def computed_subscriptions(committing_db_session, monkeypatch, embedding_api):
    """A real registered product with two ordered roots sharing dependency B."""
    first, second, dependency = sorted(uuid4() for _ in range(3))
    product_id = uuid4()
    product_name = f"Attempt freshness {product_id}"

    class ComputedSubscription(SubscriptionModel, is_base=True):
        @computed_field
        @property
        def computed_from_b(self) -> str:
            return SubscriptionModel.from_subscription(dependency).description

    class OrderedConfig(EntityConfig):
        def get_all_query(self, entity_id=None):
            return (
                super()
                .get_all_query(entity_id)
                .where(SubscriptionTable.subscription_id.in_([first, second]))
                .order_by(SubscriptionTable.subscription_id)
            )

    monkeypatch.setitem(SUBSCRIPTION_MODEL_REGISTRY, product_name, ComputedSubscription)
    monkeypatch.setitem(
        ENTITY_CONFIG_REGISTRY,
        EntityType.SUBSCRIPTION,
        OrderedConfig(
            entity_kind=EntityType.SUBSCRIPTION,
            table=SubscriptionTable,
            traverser=ENTITY_CONFIG_REGISTRY[EntityType.SUBSCRIPTION].traverser,
            pk_name="subscription_id",
            root_name="subscription",
            title_paths=["subscription.description"],
        ),
    )
    db.session.add(
        ProductTable(
            product_id=product_id,
            name=product_name,
            description="Attempt freshness",
            product_type="Test",
            tag="TEST",
            status="active",
        )
    )
    db.session.flush()
    db.session.add_all(
        SubscriptionTable(
            subscription_id=subscription_id,
            product_id=product_id,
            description=description,
            customer_id=str(uuid4()),
            insync=True,
            status="active",
        )
        for subscription_id, description in [(first, "first"), (second, "second"), (dependency, "B-old")]
    )
    db.session.commit()
    return first, second, dependency


def _stored_value(subscription_id, path="subscription.computed_from_b"):
    with db.wrapped_database.engine.connect() as reader:
        return reader.scalar(
            select(AiSearchIndex.value).where(
                AiSearchIndex.entity_type == EntityType.SUBSCRIPTION.value,
                AiSearchIndex.entity_id == subscription_id,
                AiSearchIndex.path == Ltree(path),
            )
        )


def test_bulk_computed_field_does_not_downgrade_an_already_newer_hook_value(computed_subscriptions, monkeypatch):
    """Removing the attempt boundary must let earlier-chunk B-old clobber A's B-new."""
    _, owner, dependency = computed_subscriptions
    hook_values = []

    def hook():
        with db.wrapped_database.engine.begin() as updater:
            updater.execute(
                update(SubscriptionTable)
                .where(SubscriptionTable.subscription_id == dependency)
                .values(description="B-new")
            )
        run_indexing_for_entity(EntityType.SUBSCRIPTION, str(owner))
        hook_values.append(_stored_value(owner))

    fired = False

    def embed(texts, dry_run):
        nonlocal fired
        if not fired:
            fired = True  # prevent recursion in the hook's actual indexing task
            # A separate context/session models an independent hook. B is already
            # cached by the first bulk chunk, but A's baseline has not been read.
            Context().run(hook)
        return [[] for _ in texts]

    monkeypatch.setattr(EmbeddingIndexer, "get_embeddings_from_api_batch", embed)
    run_indexing_for_entity(EntityType.SUBSCRIPTION, chunk_size=1)

    assert hook_values == ["B-new"]  # real single-entity task committed the newer A path
    assert _stored_value(owner) == "B-new"  # verified independently after bulk commits


@pytest.mark.parametrize("mode", ["plain", "force", "retry"])
def test_planning_refreshes_a_pinned_dependency_in_the_same_session(computed_subscriptions, mode):
    """Domain-cache bypass alone must not leave B's strongly pinned ORM row stale."""
    owner, _, dependency = computed_subscriptions
    session = db.session
    original_expire = session.expire_on_commit
    session.expire_on_commit = False
    try:
        with cache_subscription_models():
            pinned = SubscriptionModel.from_subscription(dependency)
            root = session.get(SubscriptionTable, owner)
            session.commit()  # idle retry Session, deliberately keeping stale ORM state
            with db.wrapped_database.engine.begin() as updater:
                updater.execute(
                    update(SubscriptionTable)
                    .where(SubscriptionTable.subscription_id == dependency)
                    .values(description="B-new")
                )
            assert pinned.description == "B-old"
            assert pinned.db_model.description == "B-old"
            indexer = Indexer(ENTITY_CONFIG_REGISTRY[EntityType.SUBSCRIPTION], False, mode == "force")
            if mode == "retry":
                indexer._dropped_entity_ids.add(str(owner))
                processed, _ = indexer._retry_dropped(session)
            else:
                processed, _, dropped = indexer._process_chunk([root], session)
                assert dropped == []
                session.commit()
            assert processed > 0
            assert get_from_cache(dependency) is pinned  # outer cache preserved, not cleared
            assert pinned.description == "B-old"
        assert _stored_value(owner) == "B-new"
    finally:
        session.expire_on_commit = original_expire


def test_clean_borrowed_planning_keeps_flushed_caller_changes(computed_subscriptions):
    """A fresh independent Session would lose the caller's uncommitted source view."""
    owner, _, _ = computed_subscriptions
    root = db.session.get(SubscriptionTable, owner)
    root.description = "caller-flushed"
    db.session.flush()
    indexer = Indexer(ENTITY_CONFIG_REGISTRY[EntityType.SUBSCRIPTION], False, False)
    fields, _, _, _ = indexer._determine_changes([root], db.session)
    assert {field.value for _, field in fields if str(field.path) == "subscription.description"} == {"caller-flushed"}
    db.session.commit()


def test_dependency_reuse_is_limited_to_one_planning_attempt(computed_subscriptions, monkeypatch):
    """A shared dependency is built once per chunk, not once for the entire run."""
    first, second, dependency = computed_subscriptions
    real_get = SubscriptionModel._get_subscription
    loads = []

    def get_subscription(cls, subscription_id):
        if subscription_id == dependency:
            loads.append(subscription_id)
        return real_get(subscription_id)

    monkeypatch.setattr(SubscriptionModel, "_get_subscription", classmethod(get_subscription))
    roots = [db.session.get(SubscriptionTable, first), db.session.get(SubscriptionTable, second)]
    indexer = Indexer(ENTITY_CONFIG_REGISTRY[EntityType.SUBSCRIPTION], False, False)
    with cache_subscription_models():
        indexer._determine_changes(roots, db.session)
        assert len(loads) == 1  # both roots share B within the same attempt
        indexer._determine_changes(roots, db.session)
        assert len(loads) == 2  # subsequent attempt cannot reuse the first one's B

    observations = {}
    for caching in [True, False]:
        selects = []

        def before_cursor(_conn, _cursor, statement, _params, _context, _many, selects=selects):
            if statement.lstrip().upper().startswith("SELECT"):
                selects.append(statement)

        db.session.expire_all()
        before_loads = len(loads)
        event.listen(db.wrapped_database.engine, "before_cursor_execute", before_cursor)
        try:
            with cache_subscription_models(fresh=True) if caching else no_subscription_model_cache():
                for _ in range(4):
                    assert SubscriptionModel.from_subscription(dependency).description == "B-old"
        finally:
            event.remove(db.wrapped_database.engine, "before_cursor_execute", before_cursor)
        observations[str(caching)] = {"domain_loads": len(loads) - before_loads, "selects": len(selects)}
    assert observations["True"]["domain_loads"] == 1
    assert observations["False"]["domain_loads"] == 4
    assert observations["True"]["selects"] < observations["False"]["selects"]
    print("CACHE_COUNTS " + json.dumps(observations, sort_keys=True))


def test_read_uncommitted_sees_commits_not_dirty_data_and_persists_index(committing_db_session, embedding_api):
    """Rejecting PostgreSQL READ UNCOMMITTED wrongly refuses statement-fresh indexing."""
    workflow_id = uuid4()
    db.session.add(
        WorkflowTable(
            workflow_id=workflow_id, name=f"attempt-isolation-{workflow_id}", target="SYSTEM", description="before"
        )
    )
    db.session.commit()
    stmt = select(WorkflowTable.description).where(WorkflowTable.workflow_id == workflow_id)
    engine = db.wrapped_database.engine
    with (
        engine.connect().execution_options(isolation_level="READ UNCOMMITTED") as connection,
        Session(connection) as session,
    ):
        assert connection.get_isolation_level() == "READ UNCOMMITTED"
        assert session.scalar(stmt) == "before"
        with engine.begin() as updater:
            updater.execute(
                update(WorkflowTable)
                .where(WorkflowTable.workflow_id == workflow_id)
                .values(description="committed-after")
            )
        assert session.scalar(stmt) == "committed-after"
        with engine.connect() as updater, updater.begin():
            updater.execute(
                update(WorkflowTable)
                .where(WorkflowTable.workflow_id == workflow_id)
                .values(description="dirty-uncommitted")
            )
            assert session.scalar(stmt) == "committed-after"
            updater.rollback()
        row = session.get(WorkflowTable, workflow_id)
        indexer = Indexer(ENTITY_CONFIG_REGISTRY[EntityType.WORKFLOW], False, False)
        processed, _, dropped = indexer._process_chunk([row], session)
        assert processed > 0
        assert dropped == []
        session.commit()
    with engine.connect() as reader:
        assert (
            reader.scalar(
                select(AiSearchIndex.value).where(
                    AiSearchIndex.entity_id == workflow_id, AiSearchIndex.path == Ltree("workflow.description")
                )
            )
            == "committed-after"
        )


@pytest.fixture
def missing_workflow(committing_db_session, embedding_api):
    """A soft-deleted source with an existing, independently committed index."""
    workflow_id = uuid4()
    db.session.add(
        WorkflowTable(
            workflow_id=workflow_id,
            name=f"missing-removal-{workflow_id}",
            target="SYSTEM",
            description="original-value",
        )
    )
    db.session.commit()
    run_indexing_for_entity(EntityType.WORKFLOW, str(workflow_id))
    with db.wrapped_database.engine.begin() as updater:
        updater.execute(
            update(WorkflowTable).where(WorkflowTable.workflow_id == workflow_id).values(deleted_at=nowtz())
        )
    return workflow_id


def _workflow_index_value(workflow_id):
    with db.wrapped_database.engine.connect() as reader:
        return reader.scalar(
            select(AiSearchIndex.value).where(
                AiSearchIndex.entity_type == EntityType.WORKFLOW.value,
                AiSearchIndex.entity_id == workflow_id,
                AiSearchIndex.path == Ltree("workflow.description"),
            )
        )


@pytest.mark.parametrize("spelling", ["canonical", "uppercase", "compact", "urn"])
def test_missing_removal_preserves_a_newer_restored_workflow_index(missing_workflow, monkeypatch, spelling):
    """A pre-lock absence observation must not delete a hook's later committed value."""
    from orchestrator.core.search.indexing import tasks

    real_lock = tasks.acquire_search_index_write_lock
    hook_values = []

    def lock_after_restore(session, entity_kind):
        with db.wrapped_database.engine.begin() as updater:
            updater.execute(
                update(WorkflowTable)
                .where(WorkflowTable.workflow_id == missing_workflow)
                .values(deleted_at=None, description="newer-hook-value")
            )
        Context().run(run_indexing_for_entity, EntityType.WORKFLOW, str(missing_workflow))
        hook_values.append(_workflow_index_value(missing_workflow))
        real_lock(session, entity_kind)

    monkeypatch.setattr(tasks, "acquire_search_index_write_lock", lock_after_restore)
    entity_id = {
        "canonical": str(missing_workflow),
        "uppercase": str(missing_workflow).upper(),
        "compact": missing_workflow.hex,
        "urn": missing_workflow.urn,
    }[spelling]
    run_indexing_for_entity(EntityType.WORKFLOW, entity_id)
    assert hook_values == ["newer-hook-value"]
    assert _workflow_index_value(missing_workflow) == "newer-hook-value"


def test_missing_removal_commits_and_releases_its_lock(missing_workflow):
    """Characterize the supported owned path, independently of refusal regressions."""
    run_indexing_for_entity(EntityType.WORKFLOW, str(missing_workflow))
    assert _workflow_index_value(missing_workflow) is None
    with db.wrapped_database.engine.begin() as reader:
        assert (
            reader.scalar(
                text("SELECT pg_try_advisory_xact_lock(hashtext('orchestrator.search.indexer'), hashtext('WORKFLOW'))")
            )
            is True
        )


@contextmanager
def _task_sessions_bound_to(monkeypatch, bind):
    """Route real public task scopes through a chosen binding, with full restoration."""
    database = db.wrapped_database
    factory = sessionmaker(bind=bind, **SESSION_ARGUMENTS)
    scoped = scoped_session(factory, database._scopefunc)
    with monkeypatch.context() as bindings:
        bindings.setattr(database, "session_factory", factory)
        bindings.setattr(database, "scoped_session", scoped)
        try:
            yield
        finally:
            scoped.remove()


@pytest.mark.parametrize("savepoint", [False, True])
def test_public_missing_removal_rejects_external_transactions(missing_workflow, monkeypatch, savepoint):
    """A Session-level removal commit cannot end its bound Connection's transaction."""
    engine = db.wrapped_database.engine
    with engine.connect() as connection, connection.begin() as outer:
        nested = connection.begin_nested() if savepoint else None
        try:
            with _task_sessions_bound_to(monkeypatch, connection):
                with pytest.raises(RuntimeError, match="externally begun transaction"):
                    run_indexing_for_entity(EntityType.WORKFLOW, str(missing_workflow))
                assert outer.is_active
                if nested is not None:
                    assert nested.is_active
                assert _workflow_index_value(missing_workflow) == "original-value"
        finally:
            if nested is not None and nested.is_active:
                nested.rollback()


@pytest.mark.parametrize("entrypoint", ["public", "direct"])
def test_public_missing_removal_rejects_autocommit_before_lock_or_delete(missing_workflow, monkeypatch, entrypoint):
    """AUTOCOMMIT must not release removal's type lock before its trigger-firing DELETE."""
    statements = []
    engine = db.wrapped_database.engine

    def observe(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement)

    autocommit_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
    database = db.wrapped_database
    real_scope = database.database_scope

    @contextmanager
    def autocommit_write_scope(**kwargs):
        # Keep the originating streaming read transactional; only the owned
        # write-scope factory uses AUTOCOMMIT, as it could in an application.
        with _task_sessions_bound_to(monkeypatch, autocommit_engine), real_scope(**kwargs) as scoped:
            yield scoped

    monkeypatch.setattr(database, "database_scope", autocommit_write_scope)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        if entrypoint == "public":
            with pytest.raises(RuntimeError, match="AUTOCOMMIT"):
                run_indexing_for_entity(EntityType.WORKFLOW, str(missing_workflow))
        else:
            with Session(autocommit_engine) as session, pytest.raises(RuntimeError, match="AUTOCOMMIT"):
                _remove_entity_from_index(EntityType.WORKFLOW, str(missing_workflow), False, session)
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert not any("pg_advisory_xact_lock" in stmt or stmt.lstrip().upper().startswith("DELETE") for stmt in statements)
    assert _workflow_index_value(missing_workflow) == "original-value"


@pytest.mark.parametrize("show_progress", [False, True])
@pytest.mark.parametrize("force_index", [False, True])
@pytest.mark.parametrize("pending_description", ["pending-only", None])
def test_public_dry_run_never_autoflushes_the_originating_session(
    computed_subscriptions, monkeypatch, show_progress, force_index, pending_description
):
    """Counting, source execution and lazy traversal must all preserve pending state."""
    owner, _, _ = computed_subscriptions
    session = db.session
    root = session.get(SubscriptionTable, owner)
    root.description = pending_description
    flushes = []

    def before_flush(*_args):
        flushes.append(True)

    def dry_run_embedding(texts, dry_run):
        assert dry_run, "public dry-run requested real embeddings"
        return [[] for _ in texts]

    event.listen(session, "before_flush", before_flush)
    monkeypatch.setattr(EmbeddingIndexer, "get_embeddings_from_api_batch", dry_run_embedding)
    try:
        run_indexing_for_entity(
            EntityType.SUBSCRIPTION,
            dry_run=True,
            force_index=force_index,
            show_progress=show_progress,
            chunk_size=1,
        )
        assert flushes == []
        assert root in session.dirty
        assert root.description == pending_description
        assert _stored_value(owner) is None
    finally:
        event.remove(session, "before_flush", before_flush)
        session.rollback()
