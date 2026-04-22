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

import strawberry
import structlog
from redis.asyncio import Redis as AIORedis

from oauth2_lib.strawberry import authenticated_mutation_field
from orchestrator.core.graphql.resolvers.helpers import make_async
from orchestrator.core.graphql.schemas.errors import Error
from orchestrator.core.graphql.schemas.settings import (
    CACHE_FLUSH_OPTIONS,
    CacheClearResponse,
    CacheClearSuccess,
    EngineSettingsType,
    StatusType,
    StatusUpdateResponse,
    WorkerStatusType,
)
from orchestrator.core.graphql.types import OrchestratorInfo
from orchestrator.core.graphql.utils import get_selected_fields
from orchestrator.core.schemas.engine_settings import WorkerStatus
from orchestrator.core.services.processes import SYSTEM_USER, ThreadPoolWorkerStatus, marshall_processes
from orchestrator.core.services.settings import (
    generate_engine_settings_schema,
    get_engine_settings_table,
    get_engine_settings_table_for_update,
    post_update_to_slack,
)
from orchestrator.core.settings import ExecutorType, app_settings
from orchestrator.core.utils.redis import delete_keys_matching_pattern
from orchestrator.core.utils.redis_client import create_redis_asyncio_client

logger = structlog.get_logger(__name__)


# Queries
@make_async
def resolve_settings(info: OrchestratorInfo) -> StatusType:
    selected_fields = get_selected_fields(info)

    db_engine_settings = get_engine_settings_table()
    pydantic_orm_resp = generate_engine_settings_schema(db_engine_settings)
    engine_settings = EngineSettingsType.from_pydantic(pydantic_orm_resp)

    settings_resp_obj = StatusType(
        engine_settings=engine_settings,
        cache_names=None,
        worker_status=None,
    )

    if "workerStatus" in selected_fields:
        worker_status: WorkerStatus
        if app_settings.EXECUTOR == ExecutorType.WORKER:
            from orchestrator.core.services.tasks import CeleryJobWorkerStatus

            worker_status = CeleryJobWorkerStatus()
        else:
            worker_status = ThreadPoolWorkerStatus()
        settings_resp_obj.worker_status = WorkerStatusType.from_pydantic(worker_status)

    if "cacheNames" in selected_fields:
        settings_resp_obj.cache_names = CACHE_FLUSH_OPTIONS  # type: ignore

    return settings_resp_obj


# Mutations
async def clear_cache(info: OrchestratorInfo, name: str) -> CacheClearSuccess | Error:
    cache: AIORedis = create_redis_asyncio_client(app_settings.CACHE_URI.get_secret_value())
    if name not in CACHE_FLUSH_OPTIONS:
        return Error(message="Invalid cache name")

    key_name = "orchestrator:*" if name == "all" else f"orchestrator:{name}:*"
    deleted = await delete_keys_matching_pattern(cache, key_name)
    return CacheClearSuccess(deleted=deleted)


async def set_status(info: OrchestratorInfo, global_lock: bool) -> Error | EngineSettingsType:
    current_engine_settings = get_engine_settings_table_for_update()

    if not (updated_engine_settings := marshall_processes(current_engine_settings, global_lock)):
        return Error(
            message="Something went wrong while updating the database aborting, possible manual intervention required",
        )
    engine_settings_schema = generate_engine_settings_schema(updated_engine_settings)
    if app_settings.SLACK_ENGINE_SETTINGS_HOOK_ENABLED:
        oidc_user = await info.context.get_current_user
        user_name = oidc_user.name if oidc_user else SYSTEM_USER
        post_update_to_slack(engine_settings_schema, user_name)

    return EngineSettingsType.from_pydantic(engine_settings_schema)


@strawberry.type(description="Settings endpoint mutations")
class SettingsMutation:
    clear_cache: CacheClearResponse = authenticated_mutation_field(
        resolver=clear_cache, description="Clear a redis cache by name"
    )
    update_status: StatusUpdateResponse = authenticated_mutation_field(
        resolver=set_status, description="Update global status of the engine"
    )
