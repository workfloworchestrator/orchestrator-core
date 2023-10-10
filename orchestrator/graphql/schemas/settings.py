from typing import Annotated, Optional, Union

import strawberry
from strawberry.scalars import JSON

from orchestrator.graphql.schemas.errors import Error
from orchestrator.schemas import WorkerStatus
from orchestrator.schemas.engine_settings import EngineSettingsSchema

CACHE_FLUSH_OPTIONS: dict[str, str] = {"all": "All caches"}


@strawberry.experimental.pydantic.type(model=WorkerStatus, all_fields=True)
class WorkerStatusType:
    pass


@strawberry.experimental.pydantic.type(model=EngineSettingsSchema, all_fields=True)
class EngineSettingsType:
    pass


@strawberry.type
class StatusType:
    engine_settings: Optional[EngineSettingsType]
    worker_status: Optional[WorkerStatusType]
    cache_names: Optional[JSON]


# Responses
@strawberry.type
class CacheClearSuccess:
    deleted: int


CacheClearResponse = Annotated[Union[CacheClearSuccess, Error], strawberry.union("CacheClearResponse")]
StatusUpdateResponse = Annotated[Union[EngineSettingsType, Error], strawberry.union("StatusUpdateResponse")]
