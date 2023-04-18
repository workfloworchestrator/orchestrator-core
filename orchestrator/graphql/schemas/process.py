import strawberry
from strawberry.scalars import JSON

from orchestrator.schemas.process import ProcessForm, ProcessSchema, ProcessStepSchema


@strawberry.experimental.pydantic.type(model=ProcessForm)
class ProcessFormType:
    title: strawberry.auto
    type: strawberry.auto
    properties: JSON
    additionalProperties: strawberry.auto
    required: strawberry.auto
    definitions: JSON | None


@strawberry.experimental.pydantic.type(
    model=ProcessStepSchema,
    fields=[
        "stepid",
        "name",
        "status",
        "created_by",
        "executed",
        "commit_hash",
    ],
)
class ProcessStepType:
    pass


@strawberry.experimental.pydantic.type(
    model=ProcessSchema,
    fields=[
        "id",
        "workflow_name",
        "product",
        "customer",
        "assignee",
        "failed_reason",
        "traceback",
        "step",
        "status",
        "last_step",
        "created_by",
        "started",
        "last_modified",
        "is_task",
        "steps",
        "form",
    ],
)
class Process:
    pass
