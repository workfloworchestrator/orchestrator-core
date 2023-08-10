from typing import TYPE_CHECKING, Annotated, List

import strawberry

from orchestrator.schemas import WorkflowSchema

if TYPE_CHECKING:
    from orchestrator.graphql.schemas.product import ProductType


@strawberry.experimental.pydantic.type(model=WorkflowSchema, all_fields=True)
class Workflow:
    @strawberry.field(description="Return all products that can use this workflow")  # type: ignore
    async def products(self) -> List[Annotated["ProductType", strawberry.lazy(".product")]]:
        from orchestrator.graphql.schemas.product import ProductType

        return [ProductType.from_pydantic(product) for product in self._original_model.products]  # type: ignore
