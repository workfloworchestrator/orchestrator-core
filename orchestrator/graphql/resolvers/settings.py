from typing import Union

import strawberry
import structlog
from oauth2_lib.graphql_authentication import authenticated_mutation_field
from redis.asyncio import Redis as AIORedis

from orchestrator.api.api_v1.endpoints.settings import generate_engine_status_response
from orchestrator.db import EngineSettingsTable
from orchestrator.graphql.schemas.errors import Error
from orchestrator.graphql.schemas.settings import (
    CACHE_FLUSH_OPTIONS,
    CacheClearResponse,
    CacheClearSuccess,
    EngineSettingsType,
    StatusType,
    StatusUpdateResponse,
    WorkerStatusType,
)
from orchestrator.graphql.types import CustomInfo
from orchestrator.graphql.utils import get_selected_fields
from orchestrator.schemas.engine_settings import EngineSettingsSchema, WorkerStatus
from orchestrator.services.processes import SYSTEM_USER, ThreadPoolWorkerStatus
from orchestrator.services.settings import marshall_processes, post_update_to_slack
from orchestrator.settings import ExecutorType, app_settings
from orchestrator.utils.redis import delete_keys_matching_pattern

logger = structlog.get_logger(__name__)


# Queries
def resolve_settings(info: CustomInfo) -> StatusType:
    selected_fields = get_selected_fields(info)

    db_engine_settings = EngineSettingsTable.query.one()
    pydantic_orm_resp = generate_engine_status_response(db_engine_settings)
    engine_settings = EngineSettingsType.from_pydantic(pydantic_orm_resp)

    settings_resp_obj = StatusType(
        engine_settings=engine_settings,
        cache_names=None,
        worker_status=None,
    )

    if "workerStatus" in selected_fields:
        worker_status: WorkerStatus
        if app_settings.EXECUTOR == ExecutorType.WORKER:
            from orchestrator.services.tasks import CeleryJobWorkerStatus

            worker_status = CeleryJobWorkerStatus()
        else:
            worker_status = ThreadPoolWorkerStatus()
        settings_resp_obj.worker_status = WorkerStatusType.from_pydantic(worker_status)

    if "cacheNames" in selected_fields:
        settings_resp_obj.cache_names = CACHE_FLUSH_OPTIONS

    return settings_resp_obj


# Mutations
async def clear_cache(info: CustomInfo, name: str) -> Union[CacheClearSuccess, Error]:
    cache: AIORedis = AIORedis(host=app_settings.CACHE_HOST, port=app_settings.CACHE_PORT)
    if name not in CACHE_FLUSH_OPTIONS:
        return Error(message="Invalid cache name")

    key_name = "orchestrator:*" if name == "all" else f"orchestrator:{name}:*"
    deleted = await delete_keys_matching_pattern(cache, key_name)
    return CacheClearSuccess(deleted=deleted)


def set_status(info: CustomInfo, global_lock: bool) -> Union[Error, EngineSettingsType]:
    engine_settings = EngineSettingsTable.query.with_for_update().one()

    result = marshall_processes(engine_settings, global_lock)
    if not result:
        return Error(
            message="Something went wrong while updating the database aborting, possible manual intervention required",
        )
    if app_settings.SLACK_ENGINE_SETTINGS_HOOK_ENABLED:
        oidc_user = info.context.get_current_user()
        user_name = oidc_user.name if oidc_user else SYSTEM_USER
        post_update_to_slack(EngineSettingsSchema.from_orm(result), user_name)

    status_response = generate_engine_status_response(result)
    return EngineSettingsType.from_pydantic(status_response)


@strawberry.type(description="Settings endpoint mutations")
class SettingsMutation:
    clear_cache: CacheClearResponse = authenticated_mutation_field(
        resolver=clear_cache, description="Clear a redis cache by name"
    )
    update_status: StatusUpdateResponse = authenticated_mutation_field(
        resolver=set_status, description="Update global status of the engine"
    )
