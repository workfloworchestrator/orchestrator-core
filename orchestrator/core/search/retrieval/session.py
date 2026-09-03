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

from collections.abc import Sequence

import structlog
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.search.retrieval.retrievers.base import SessionSetting

logger = structlog.get_logger(__name__)

# Settings the database refused, so the warning is logged once per process instead of once per search.
_rejected_session_settings: set[str] = set()


async def apply_session_settings(db_session: AsyncSession, settings: Sequence[SessionSetting]) -> None:
    """Apply ``SET LOCAL`` settings, which last for the search transaction and no longer.

    Each setting runs in its own savepoint so a value the server rejects does not abort the search
    transaction, and rolling that savepoint back also undoes the setting. Rejection happens on
    pgvector < 0.8, which reserves the ``hnsw`` prefix but does not define ``hnsw.iterative_scan``:
    the search then runs without it, returning fewer semantic candidates rather than failing.
    Rejections are logged once per setting per process.
    """
    for setting in settings:
        try:
            async with db_session.begin_nested():
                await db_session.execute(text(setting.statement))
        except DBAPIError as exc:
            if setting.name not in _rejected_session_settings:
                _rejected_session_settings.add(setting.name)
                logger.warning(
                    "Search session setting rejected by the database; continuing without it",
                    setting=setting.name,
                    value=setting.value,
                    error=str(exc.orig),
                )


__all__ = ["apply_session_settings"]
