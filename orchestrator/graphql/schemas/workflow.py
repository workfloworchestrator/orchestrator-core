import strawberry

from orchestrator.schemas import WorkflowSchema


@strawberry.experimental.pydantic.type(model=WorkflowSchema, all_fields=True)
class Workflow:
    pass
