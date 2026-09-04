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

import contextlib
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from orchestrator.core.db import db


@contextlib.asynccontextmanager
async def session_joined_async() -> AsyncIterator[AsyncSession]:
    """AsyncSession bound to the per-test transaction opened by ``db_session``.

    ``db.async_session()`` uses the async engine's own connection pool, so its commits are real
    and escape ``db_session``'s rollback, leaking into later tests. Binding an ``AsyncConnection``
    to the already-open sync test connection and joining it via a savepoint keeps this session's
    work inside that same outer transaction, so it rolls back with everything else.
    """
    async_connection = AsyncConnection(db.wrapped_database.async_engine, sync_connection=db.session.connection()) # type: ignore
    async with AsyncSession(
        bind=async_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        yield session
