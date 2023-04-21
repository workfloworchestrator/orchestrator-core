import strawberry

from orchestrator.schemas.resource_type import ResourceTypeSchema


@strawberry.experimental.pydantic.type(model=ResourceTypeSchema)
class ResourceType:
    resource_type: strawberry.auto
    description: str | None
    resource_type_id: strawberry.auto
