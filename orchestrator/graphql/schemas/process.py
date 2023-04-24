import strawberry
from strawberry.scalars import JSON

from orchestrator.db.sql_models import ProcessSQLModel, StepSQLModel
from orchestrator.schemas.process import ProcessForm


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


@strawberry.experimental.pydantic.type(  # type: ignore
    model=StepSQLModel,
    fields=[
        "stepid",
        "name",
        "status",
        "created_by",
        "executed_at",
        "commit_hash",
    ],
)
class ProcessStepType:
    state: JSON | None


@strawberry.experimental.pydantic.type(model=ProcessSQLModel, all_fields=True)  # type: ignore
class ProcessType:
    product_id: str | None
    customer_id: str | None
    current_state: JSON | None
    form: JSON | None
    steps: list[ProcessStepType]

    @strawberry.field(description="Process subscriptions")
    async def subscriptions(self) -> str:
        return "the to implement subscriptions model list"
