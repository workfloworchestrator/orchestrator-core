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

import pytest
from sqlalchemy import select

from orchestrator.core.db import ProductTable, db, get_async_session
from orchestrator.core.db.database import WrappedSession


async def test_async_session_executes_queries():
    async with db.async_session() as session:
        assert (await session.execute(select(1))).scalar_one() == 1
        product_names = (await session.scalars(select(ProductTable.name).limit(1))).all()
    assert isinstance(product_names, list)


def test_async_engine_targets_same_database_with_same_driver():
    assert db.async_engine.url == db.engine.url


async def test_async_session_commit_honors_disable_commit():
    """The commit-disable safeguard used by ``transactional()`` must also work through async sessions."""
    async with db.async_session() as session:
        sync_session = session.sync_session
        assert isinstance(sync_session, WrappedSession)

        await session.execute(select(1))
        sync_session.disable_commit()
        await session.commit()
        assert session.in_transaction(), "commit() must be swallowed while commits are disabled"

        sync_session.enable_commit()
        await session.commit()
        assert not session.in_transaction()


async def test_get_async_session_dependency_closes_the_session_after_use():
    dependency = get_async_session()
    session = await anext(dependency)
    assert (await session.execute(select(1))).scalar_one() == 1
    assert session.in_transaction()

    with pytest.raises(StopAsyncIteration):
        await anext(dependency)
    assert not session.in_transaction()
