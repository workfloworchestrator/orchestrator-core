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

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import DBAPIError

from orchestrator.core.search.retrieval import session as retrieval_session
from orchestrator.core.search.retrieval.retrievers.base import HNSW_ITERATIVE_SCAN, SessionSetting

OTHER_SETTING = SessionSetting("hnsw.ef_search", "100")


class _FakeSavepoint:
    """Stands in for `AsyncSession.begin_nested()`, which is an async context manager."""

    def __init__(self, session: "_FakeSession") -> None:
        self._session = session

    async def __aenter__(self) -> "_FakeSavepoint":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None:
            self._session.rolled_back.append(exc_type)
        return False


class _FakeSession:
    def __init__(self, reject: set[str] | None = None) -> None:
        self.reject = reject or set()
        self.executed: list[str] = []
        self.rolled_back: list[type] = []

    def begin_nested(self) -> _FakeSavepoint:
        return _FakeSavepoint(self)

    async def execute(self, statement):
        sql = str(statement)
        self.executed.append(sql)
        if any(name in sql for name in self.reject):
            raise DBAPIError("SET LOCAL", {}, Exception("unrecognized configuration parameter"))
        return MagicMock()


@pytest.fixture(autouse=True)
def _forget_rejected_settings():
    """The warn-once cache is process global; keep tests independent of each other."""
    retrieval_session._rejected_session_settings.clear()
    yield
    retrieval_session._rejected_session_settings.clear()


@pytest.mark.parametrize(
    "settings",
    [
        pytest.param((), id="nothing_to_apply"),
        pytest.param((HNSW_ITERATIVE_SCAN, OTHER_SETTING), id="each_as_set_local"),
    ],
)
async def test_settings_are_applied_as_set_local(settings):
    """SET LOCAL lasts for the transaction, which is exactly the lifetime the search needs."""
    session = _FakeSession()

    await retrieval_session.apply_session_settings(session, settings)

    assert session.executed == [f"SET LOCAL {s.name} = '{s.value}'" for s in settings]


async def test_a_rejected_setting_is_skipped_and_warned_about_once():
    """Pgvector < 0.8 rejects the value; the search must still run, later settings still apply."""
    session = _FakeSession(reject={HNSW_ITERATIVE_SCAN.name})

    for _ in range(3):
        await retrieval_session.apply_session_settings(session, (HNSW_ITERATIVE_SCAN, OTHER_SETTING))

    assert session.rolled_back == [DBAPIError] * 3, "each rejection rolls back only its own savepoint"
    assert sum(OTHER_SETTING.name in sql for sql in session.executed) == 3
    assert retrieval_session._rejected_session_settings == {HNSW_ITERATIVE_SCAN.name}
