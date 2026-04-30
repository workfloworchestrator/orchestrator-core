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

from typing import Annotated, Union

import strawberry
from strawberry.scalars import JSON

from orchestrator.core.graphql.schemas.errors import Error
from orchestrator.core.schemas import WorkerStatus
from orchestrator.core.schemas.engine_settings import EngineSettingsSchema

CACHE_FLUSH_OPTIONS: dict[str, str] = {"all": "All caches"}


@strawberry.experimental.pydantic.type(model=WorkerStatus, all_fields=True)
class WorkerStatusType:
    pass


@strawberry.experimental.pydantic.type(model=EngineSettingsSchema, all_fields=True)
class EngineSettingsType:
    pass


@strawberry.type
class StatusType:
    engine_settings: EngineSettingsType | None
    worker_status: WorkerStatusType | None
    cache_names: JSON | None


# Responses
@strawberry.type
class CacheClearSuccess:
    deleted: int


CacheClearResponse = Annotated[Union[CacheClearSuccess, Error], strawberry.union("CacheClearResponse")]
StatusUpdateResponse = Annotated[Union[EngineSettingsType, Error], strawberry.union("StatusUpdateResponse")]
