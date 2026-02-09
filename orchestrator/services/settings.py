# Copyright 2019-2020 SURF.
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


import requests
import structlog
from requests.exceptions import RequestException
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from orchestrator.db import EngineSettingsTable, ProcessTable, db
from orchestrator.schemas.engine_settings import EngineSettingsSchema, GlobalStatusEnum
from orchestrator.settings import app_settings

logger = structlog.get_logger(__name__)


def get_engine_settings() -> EngineSettingsTable:
    """Returns the EngineSettingsTable object. Raises an exception if the query does not return exactly one row."""
    return db.session.execute(select(EngineSettingsTable)).scalar_one()


def get_engine_settings_for_update() -> EngineSettingsTable:
    """Same as get_engine_settings but blocks until transactions on engine_settings table are committed."""
    return db.session.execute(select(EngineSettingsTable).with_for_update()).scalar_one()


def get_actual_running_processes_count() -> int:
    """Get the actual count of running processes from the database.

    This is more reliable than the running_processes counter in EngineSettingsTable,
    which uses a flawed increment/decrement mechanism that can drift over time.

    A process is considered "running" if it's in any active state in the database
    (not completed/failed/aborted), regardless of whether it's currently executing in a thread.
    This includes processes that are paused by the global lock but still have active status.

    This choice was made because:
    1. It accurately reflects the database state (source of truth)
    2. It's more reliable than thread-based counting
    3. It matches user expectations when viewing the UI
    4. When the engine is paused, users need to know how many processes are pending

    Active states include: created, running, suspended, waiting, awaiting_callback, and resumed.

    Returns:
        The actual number of processes with an active status
    """
    # Import here to avoid circular dependency (orchestrator.workflow imports from this module)
    from orchestrator.workflow import ProcessStatus

    # Define the terminal (non-running) statuses using the ProcessStatus enum
    terminal_statuses = [
        ProcessStatus.COMPLETED,
        ProcessStatus.FAILED,
        ProcessStatus.ABORTED,
        ProcessStatus.API_UNAVAILABLE,
        ProcessStatus.INCONSISTENT_DATA,
    ]

    return db.session.execute(
        select(func.count()).select_from(ProcessTable).where(ProcessTable.last_status.not_in(terminal_statuses))
    ).scalar_one()


def generate_engine_global_status(engine_settings: EngineSettingsTable) -> GlobalStatusEnum:
    """Returns the global status of the engine.

    This function queries the actual count of running processes from the database
    instead of relying on the flawed increment/decrement counter in engine_settings.running_processes.

    Note: When the engine is locked (paused), processes stop executing but may still
    have active status in the database. We count these as "running" because they represent
    pending work that will resume when the lock is released. This gives users accurate
    visibility into how many processes are pending.

    See: https://github.com/workfloworchestrator/orchestrator-core/issues/1258
    """
    running_count = get_actual_running_processes_count()

    if engine_settings.global_lock and running_count > 0:
        return GlobalStatusEnum.PAUSING
    if engine_settings.global_lock and running_count == 0:
        return GlobalStatusEnum.PAUSED
    return GlobalStatusEnum.RUNNING


def post_update_to_slack(engine_status: EngineSettingsSchema, user: str) -> None:
    """Post engine settings update to slack.

    Args:
        engine_status: EngineStatus
        user: The user who executed the change

    Returns:
        None

    """
    try:
        if engine_status.global_lock is True:
            action = f"stopped the `{app_settings.ENVIRONMENT}` workflow engine. The orchestrator will pause all running processes."
        else:
            action = f"started the `{app_settings.ENVIRONMENT}` workflow engine. The orchestrator will pick up all pending processes."

        message = {"text": f"User `{user}` {action}"}
        requests.post(app_settings.SLACK_ENGINE_SETTINGS_HOOK_URL, json=message, timeout=5)

    # Catch all Request exceptions and log. Then pass
    except RequestException:
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
