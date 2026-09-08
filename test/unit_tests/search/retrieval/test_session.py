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

"""Transaction-local Postgres settings applied before a search runs."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.search.retrieval import session as retrieval_session
from orchestrator.core.search.retrieval.session import HNSW_ITERATIVE_SCAN, SessionSetting

OTHER_SETTING = SessionSetting("hnsw.ef_search", "100")


@pytest.fixture(autouse=True)
def _forget_rejected_settings(monkeypatch):
    """The warn-once cache is process global; keep tests independent of each other."""
    monkeypatch.setattr(retrieval_session, "_rejected_session_settings", set())


async def test_settings_are_applied_as_set_local():
    """SET LOCAL lasts for the transaction, which is exactly the lifetime the search needs."""
    session = AsyncMock(spec=AsyncSession)
    settings = (HNSW_ITERATIVE_SCAN, OTHER_SETTING)

    await retrieval_session.apply_session_settings(session, settings)

    executed = [str(call.args[0]) for call in session.execute.await_args_list]
    assert executed == [f"SET LOCAL {s.name} = '{s.value}'" for s in settings]
    assert session.begin_nested.call_count == len(settings)


async def test_a_rejected_setting_is_skipped_and_warned_about_once(monkeypatch):
    """Pgvector < 0.8 rejects the value; the search must still run, later settings still apply."""
    session = AsyncMock(spec=AsyncSession)
    warning = MagicMock()
    monkeypatch.setattr(retrieval_session.logger, "warning", warning)

    async def reject_hnsw(statement):
        if HNSW_ITERATIVE_SCAN.name in str(statement):
            raise DBAPIError("SET LOCAL", {}, Exception("unrecognized configuration parameter"))

    session.execute.side_effect = reject_hnsw

    for _ in range(3):
        await retrieval_session.apply_session_settings(session, (HNSW_ITERATIVE_SCAN, OTHER_SETTING))

    executed = [str(call.args[0]) for call in session.execute.await_args_list]
    assert session.begin_nested.call_count == 6
    assert sum(OTHER_SETTING.name in sql for sql in executed) == 3
    warning.assert_called_once()
