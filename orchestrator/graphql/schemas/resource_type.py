from typing import Optional

import strawberry

from orchestrator.schemas.resource_type import ResourceTypeSchema


@strawberry.experimental.pydantic.type(model=ResourceTypeSchema)
class ResourceType:
    resource_type: strawberry.auto
    description: Optional[str]
    resource_type_id: strawberry.auto
