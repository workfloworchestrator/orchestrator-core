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
from http import HTTPStatus

import structlog
from fastapi import Query, WebSocket
from fastapi.param_functions import Depends
from fastapi.routing import APIRouter
from redis.asyncio import Redis as AIORedis
from sqlalchemy.exc import SQLAlchemyError

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.api.error_handling import raise_status
from orchestrator.db import EngineSettingsTable
from orchestrator.schemas import EngineSettingsBaseSchema, EngineSettingsSchema, GlobalStatusEnum, WorkerStatus
from orchestrator.security import authenticate
from orchestrator.services import processes, settings
from orchestrator.settings import ExecutorType, app_settings
from orchestrator.utils.json import json_dumps
from orchestrator.utils.redis import delete_keys_matching_pattern
from orchestrator.websocket import WS_CHANNELS, broadcast_invalidate_cache, websocket_manager

router = APIRouter()
logger = structlog.get_logger()


CACHE_FLUSH_OPTIONS: dict[str, str] = {
    "all": "All caches",
}


@router.delete("/cache/{name}")
async def clear_cache(name: str) -> int | None:
    cache: AIORedis = AIORedis.from_url(str(app_settings.CACHE_URI))
    if name not in CACHE_FLUSH_OPTIONS:
        raise_status(HTTPStatus.BAD_REQUEST, "Invalid cache name")

    key_name = "orchestrator:*" if name == "all" else f"orchestrator:{name}:*"
    return await delete_keys_matching_pattern(cache, key_name)


@router.get("/cache-names")
def get_cache_names() -> dict[str, str]:
    return CACHE_FLUSH_OPTIONS


@router.post("/search-index/reset")
async def reset_search_index() -> None:
    try:
        settings.reset_search_index(tx_commit=True)
    except SQLAlchemyError:
        raise_status(HTTPStatus.INTERNAL_SERVER_ERROR)


@router.put("/status", response_model=EngineSettingsSchema)
async def set_global_status(
    body: EngineSettingsBaseSchema, user: OIDCUserModel | None = Depends(authenticate)
) -> EngineSettingsSchema:
    """Update the global status of the engine to a new state.

    Args:
        body: The GlobalStatus object
        user: The OIDCUser model

    Returns:
        The updated global status object

    """

    engine_settings = settings.get_engine_settings_for_update()

    result = processes.marshall_processes(engine_settings, body.global_lock)
    if not result:
        raise_status(
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Something went wrong while updating the database aborting, possible manual intervention required",
        )
    if app_settings.SLACK_ENGINE_SETTINGS_HOOK_ENABLED:
        user_name = user.user_name if user else processes.SYSTEM_USER
        settings.post_update_to_slack(EngineSettingsSchema.model_validate(result), user_name)

    status_response = generate_engine_status_response(result)
    if websocket_manager.enabled:
        # send engine status to socket.
        await websocket_manager.broadcast_data(
            [WS_CHANNELS.ENGINE_SETTINGS],
            {"engine-status": generate_engine_status_response(result)},
        )
        await broadcast_invalidate_cache({"type": "engineStatus"})
    return status_response


@router.get("/worker-status", response_model=WorkerStatus)
def get_worker_status() -> WorkerStatus:
    """Return data on job workers and queues.

    Returns:
    - The number of queued jobs
    - The number of workers
    - The number of running jobs
    - The number of successful and unsuccessful jobs
    """

    if app_settings.EXECUTOR == ExecutorType.WORKER:
        from orchestrator.services.tasks import CeleryJobWorkerStatus

        return CeleryJobWorkerStatus()
    return processes.ThreadPoolWorkerStatus()


@router.get("/status", response_model=EngineSettingsSchema)
def get_global_status() -> EngineSettingsSchema:
    """Retrieve the global status object.

    Returns:
        The global status of the engine

    """
    engine_settings = settings.get_engine_settings()
    return generate_engine_status_response(engine_settings)


ws_router = APIRouter()


if app_settings.ENABLE_WEBSOCKETS:

    @ws_router.websocket("/ws-status/")
    async def websocket_get_global_status(websocket: WebSocket, token: str = Query(...)) -> None:
        error = await websocket_manager.authorize(websocket, token)

        await websocket.accept()
        if error:
            await websocket_manager.disconnect(websocket, reason=error)
            return

        engine_settings = settings.get_engine_settings()

        await websocket.send_text(json_dumps({"engine-status": generate_engine_status_response(engine_settings)}))

        channel = WS_CHANNELS.ENGINE_SETTINGS
        await websocket_manager.connect(websocket, channel)


def generate_engine_status_response(
    engine_settings: EngineSettingsTable,
) -> EngineSettingsSchema:
    """Generate the correct engine status response.

    Args:
        engine_settings: Engine settings database object

    Returns:
        Engine StatusEnum

    """

    if engine_settings.global_lock and engine_settings.running_processes > 0:
        result = EngineSettingsSchema.model_validate(engine_settings)
        result.global_status = GlobalStatusEnum.PAUSING
        return result

    if engine_settings.global_lock and engine_settings.running_processes == 0:
        result = EngineSettingsSchema.model_validate(engine_settings)
        result.global_status = GlobalStatusEnum.PAUSED
        return result

    result = EngineSettingsSchema.model_validate(engine_settings)
    result.global_status = GlobalStatusEnum.RUNNING
    return result
