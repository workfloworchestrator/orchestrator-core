import strawberry
from strawberry.scalars import JSON

from orchestrator.schemas.process import ProcessForm, ProcessSchema, ProcessStepSchema


@strawberry.experimental.pydantic.type(
    model=ProcessForm,
    fields=[
        "title",
        "type",
        "additionalProperties",
        "required",
    ],
)
class ProcessFormType:
    properties: JSON
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
    state: JSON | None


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
class ProcessType:
    pass
