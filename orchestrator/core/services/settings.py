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


import httpx
import requests
import structlog
from requests.exceptions import RequestException
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.db import EngineSettingsTable, db
from orchestrator.core.schemas.engine_settings import EngineSettingsSchema, GlobalStatusEnum
from orchestrator.core.services.worker_status_monitor import get_worker_status_monitor
from orchestrator.core.settings import app_settings

logger = structlog.get_logger(__name__)


def get_engine_settings_table() -> EngineSettingsTable:
    """Returns the EngineSettingsTable object. Raises an exception if the query does not return exactly one row."""
    return db.session.execute(select(EngineSettingsTable)).scalar_one()


async def get_engine_settings_table_async(session: AsyncSession) -> EngineSettingsTable:
    """Async counterpart of ``get_engine_settings_table``, for endpoints using an ``AsyncSession``."""
    result = await session.execute(select(EngineSettingsTable))
    return result.scalar_one()


def get_engine_settings_table_for_update() -> EngineSettingsTable:
    """Same as get_engine_settings but blocks until transactions on engine_settings table are committed."""
    return db.session.execute(select(EngineSettingsTable).with_for_update()).scalar_one()


def generate_engine_global_status(engine_settings: EngineSettingsTable, running_count: int) -> GlobalStatusEnum:
    """Returns the global status of the engine.

    Args:
        engine_settings: Engine settings database object
        running_count: Count of currently running processes from worker monitor

    Returns:
        The global status enum
    """
    if engine_settings.global_lock and running_count > 0:
        return GlobalStatusEnum.PAUSING
    if engine_settings.global_lock and running_count == 0:
        return GlobalStatusEnum.PAUSED
    return GlobalStatusEnum.RUNNING


def _engine_status_slack_message(engine_status: EngineSettingsSchema, user: str) -> dict[str, str]:
    """Build the Slack message body announcing an engine settings update."""
    if engine_status.global_lock is True:
        action = f"stopped the `{app_settings.ENVIRONMENT}` workflow engine. The orchestrator will pause all running processes."
    else:
        action = f"started the `{app_settings.ENVIRONMENT}` workflow engine. The orchestrator will pick up all pending processes."

    return {"text": f"User `{user}` {action}"}


def post_update_to_slack(engine_status: EngineSettingsSchema, user: str) -> None:
    """Post engine settings update to slack.

    Args:
        engine_status: EngineStatus
        user: The user who executed the change

    Returns:
        None

    """
    try:
        message = _engine_status_slack_message(engine_status, user)
        requests.post(app_settings.SLACK_ENGINE_SETTINGS_HOOK_URL, json=message, timeout=5)

    # Catch all Request exceptions and log. Then pass
    except RequestException:
        logger.exception("Post to slack failed.")
        pass


async def post_update_to_slack_async(engine_status: EngineSettingsSchema, user: str) -> None:
    """Async Post engine settings update to slack.

    Args:
        engine_status: EngineStatus
        user: The user who executed the change

    Returns:
        None

    """
    try:
        message = _engine_status_slack_message(engine_status, user)
        async with httpx.AsyncClient() as client:
            await client.post(app_settings.SLACK_ENGINE_SETTINGS_HOOK_URL, json=message, timeout=5)

    # Catch all Request exceptions and log. Then pass
    except httpx.RequestError:
        logger.exception("Post to slack failed.")
        pass


def reset_search_index(*, tx_commit: bool = False) -> None:
    try:
        db.session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY subscriptions_search;"))
    except SQLAlchemyError as e:
        logger.error("Something went wrong while refreshing materialized view", msg=str(e))
        raise e
    finally:
        if tx_commit:
            db.session.commit()
    return


async def reset_search_index_async(session: AsyncSession, *, tx_commit: bool = False) -> None:
    """Async counterpart of ``reset_search_index``, for endpoints using an ``AsyncSession``."""
    try:
        await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY subscriptions_search;"))
    except SQLAlchemyError as e:
        logger.error("Something went wrong while refreshing materialized view", msg=str(e))
        raise e
    finally:
        if tx_commit:
            await session.commit()
    return


def generate_engine_settings_schema(
    engine_settings: EngineSettingsTable,
) -> EngineSettingsSchema:
    """Generate the correct engine status schema.

    Args:
        engine_settings: Engine settings database object
    """
    monitor = get_worker_status_monitor()
    running_count = monitor.get_running_jobs_count()
    global_status = generate_engine_global_status(engine_settings, running_count)

    return EngineSettingsSchema(
        global_lock=engine_settings.global_lock,
        global_status=global_status,
        running_processes=running_count,
    )
