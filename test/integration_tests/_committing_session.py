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

"""Opt-in real commits for indexing tests that exercise transaction/lock ownership."""

from collections.abc import Iterator

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, close_all_sessions, scoped_session, sessionmaker

from orchestrator.core.db import db
from orchestrator.core.db.database import SESSION_ARGUMENTS, BaseModel
from orchestrator.core.db.models import (
    AiSearchIndex,
    APSchedulerJobStoreModel,
    ProcessTable,
    ProductBlockTable,
    ProductTable,
    ResourceTypeTable,
    SubscriptionTable,
    WorkflowTable,
)


@pytest.fixture
def committing_db_session(db_session) -> Iterator[None]:
    """Use engine-bound ambient sessions and explicitly remove these tests' committed data.

    Only indexing tests opt in. The ordinary fixture's external transaction stays
    untouched, but newly created scopes no longer join it. These are the root models
    created by the opting-in tests; ORM deletion cleans their dependent rows, and
    deleting index rows first lets the path-maintenance trigger undo their refcounts.
    This is not a general-purpose replacement for the rollback fixture.
    """
    database = db.wrapped_database
    factory, scoped = database.session_factory, database.scoped_session
    cleanup_order = (
        AiSearchIndex,
        ProcessTable,
        SubscriptionTable,
        ProductTable,
        ProductBlockTable,
        ResourceTypeTable,
        APSchedulerJobStoreModel,
        WorkflowTable,
    )
    with database.engine.connect() as connection:
        existing = {
            model: {tuple(map(str, row)) for row in connection.execute(select(*inspect(model).primary_key))}
            for model in cleanup_order
        }

    database.session_factory = sessionmaker(bind=database.engine, **SESSION_ARGUMENTS)
    database.scoped_session = scoped_session(database.session_factory, database._scopefunc)
    try:
        BaseModel.set_query(database.scoped_session.query_property())
        yield
    finally:
        try:
            database.scoped_session.remove()
            close_all_sessions()
            with Session(database.engine) as cleanup, cleanup.begin():
                for model in cleanup_order:
                    for row in cleanup.scalars(select(model)).unique():
                        if tuple(map(str, inspect(row).identity)) not in existing[model]:
                            cleanup.delete(row)
                    cleanup.flush()
        finally:
            database.session_factory, database.scoped_session = factory, scoped
            BaseModel.set_query(scoped.query_property())
