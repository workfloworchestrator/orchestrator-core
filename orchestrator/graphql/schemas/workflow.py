from typing import TYPE_CHECKING, Annotated

import strawberry

from orchestrator.config.assignee import Assignee
from orchestrator.db import WorkflowTable
from orchestrator.graphql.schemas.helpers import get_original_model
from orchestrator.graphql.types import OrchestratorInfo
from orchestrator.schemas import StepSchema, WorkflowSchema
from orchestrator.workflows import get_workflow

if TYPE_CHECKING:
    from orchestrator.graphql.schemas.product import ProductType


@strawberry.experimental.pydantic.type(model=StepSchema, all_fields=True)
class Step:
    assignee: Assignee | None


@strawberry.experimental.pydantic.type(model=WorkflowSchema, all_fields=True)
class Workflow:
    @strawberry.field(description="Return all products that can use this workflow")  # type: ignore
    async def products(self) -> list[Annotated["ProductType", strawberry.lazy(".product")]]:
        from orchestrator.graphql.schemas.product import ProductType

        model = get_original_model(self, WorkflowTable)

        return [ProductType.from_pydantic(product) for product in model.products]

    @strawberry.field(description="Return all steps for this workflow")  # type: ignore
    def steps(self) -> list[Step]:
        return [Step(name=step.name, assignee=step.assignee) for step in get_workflow(self.name).steps]  # type: ignore

    @strawberry.field(description="Return whether the currently logged-in used is allowed to start this workflow")  # type: ignore
    def is_allowed(self, info: OrchestratorInfo) -> bool:
        oidc_user = info.context.get_current_user
        workflow_table = get_original_model(self, WorkflowTable)
        workflow = get_workflow(workflow_table.name)

        return workflow.authorize_callback(oidc_user)  # type: ignore
