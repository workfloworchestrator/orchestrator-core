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
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from orchestrator.db import EngineSettingsTable, db
from orchestrator.schemas.engine_settings import EngineSettingsSchema, GlobalStatusEnum
from orchestrator.settings import app_settings

logger = structlog.get_logger(__name__)


def get_engine_settings() -> EngineSettingsTable:
    """Returns the EngineSettingsTable object. Raises an exception if the query does not return exactly one row."""
    return db.session.execute(select(EngineSettingsTable)).scalar_one()


def get_engine_settings_for_update() -> EngineSettingsTable:
    """Same as get_engine_settings but blocks until transactions on engine_settings table are committed."""
    return db.session.execute(select(EngineSettingsTable).with_for_update()).scalar_one()


def generate_engine_global_status(engine_settings: EngineSettingsTable) -> GlobalStatusEnum:
    """Returns the global status of the engine."""
    if engine_settings.global_lock and engine_settings.running_processes > 0:
        return GlobalStatusEnum.PAUSING
    if engine_settings.global_lock and engine_settings.running_processes == 0:
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
