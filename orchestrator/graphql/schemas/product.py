import strawberry

from orchestrator.graphql.schemas.fixed_input import FixedInput
from orchestrator.graphql.schemas.product_block import ProductBlock
from orchestrator.graphql.schemas.workflow import Workflow
from orchestrator.schemas.product import ProductSchema


@strawberry.experimental.pydantic.type(model=ProductSchema)
class ProductType:
    product_id: strawberry.auto
    name: strawberry.auto
    description: strawberry.auto
    product_type: strawberry.auto
    status: strawberry.auto
    tag: strawberry.auto
    created_at: strawberry.auto
    end_date: strawberry.auto
    product_blocks: list[ProductBlock]
    fixed_inputs: list[FixedInput]
    workflows: list[Workflow]
