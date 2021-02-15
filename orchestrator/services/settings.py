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

from typing import Optional

import requests
import structlog
from requests.exceptions import RequestException
from sqlalchemy.exc import SQLAlchemyError

from orchestrator.db import EngineSettingsTable, ProcessTable, db
from orchestrator.schemas.engine_settings import EngineSettingsSchema
from orchestrator.services.processes import SYSTEM_USER, resume_process
from orchestrator.settings import app_settings

logger = structlog.get_logger(__name__)


def post_update_to_slack(engine_status: EngineSettingsSchema, user: str) -> None:
    """
    Post engine settings update to slack.

    Args:
        engine_status: EngineStatus

    Returns:
        None

    """
    try:
        if engine_status.global_lock is True:
            action = f"stopped the `{app_settings.ENVIRONMENT}` workflow engine. The orchestrator will pause all running processes."
        else:
            action = f"started the `{app_settings.ENVIRONMENT}` workflow engine. The orchestrator will pick up all pending processes."

        message = {"text": f"User `{user}` {action}"}
        requests.post(app_settings.SLACK_ENGINE_SETTINGS_HOOK_URL, json=message)

    # Catch all Request exceptions and log. Then pass
    except RequestException:
        logger.exception("Post to slack failed.")
        pass


def marshall_processes(engine_settings: EngineSettingsTable, new_global_lock: bool) -> Optional[EngineSettingsTable]:
    """
    Manage processes depending on the engine status.

    This function only has to act when in the transitioning fases, i.e Pausing and Starting

    Args:
        engine_settings: Engine status containing the lock and status fields
        new_global_lock: The state to which needs to be transitioned

    Returns:
        Engine status or none

    """
    try:
        # This is the first process/container that will pick up the "running" queue
        if engine_settings.global_lock and not new_global_lock:
            # Update the global lock to unlocked, to make sure no one else picks up the queue
            engine_settings.global_lock = new_global_lock
            db.session.commit()

            # Resume all the running processes
            running_processes = ProcessTable.query.filter(ProcessTable.last_status == "running").all()
            for process in running_processes:
                resume_process(process, user=SYSTEM_USER)

        elif not engine_settings.global_lock and new_global_lock:
            # Lock the engine
            logger.info("Locking the orchestrator engine, Processes will run until the next step")
            engine_settings.global_lock = new_global_lock
            db.session.commit()
        else:
            logger.info(
                "Engine is already locked or unlocked, global lock is unchanged",
                global_lock=engine_settings.global_lock,
                new_status=new_global_lock,
            )

        return engine_settings

    except SQLAlchemyError:
        logger.exception("Encountered a database error, aborting and stopping. Health check will crash the app")
        return None
    except ValueError:
        logger.exception("Encountered an anomaly, locking the engine; manual intervention necessary to fix")
        engine_settings.global_lock = True
        db.session.commit()
        return None
