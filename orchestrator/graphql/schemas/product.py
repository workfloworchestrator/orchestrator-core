import strawberry

from orchestrator.graphql.schemas.fixed_input import FixedInputType
from orchestrator.graphql.schemas.product_block import ProductBlockType
from orchestrator.schemas.product import ProductSchema


@strawberry.experimental.pydantic.type(model=ProductSchema)
class ProductBaseType:
    product_id: strawberry.auto
    name: strawberry.auto
    description: strawberry.auto
    product_type: strawberry.auto
    status: strawberry.auto
    tag: strawberry.auto
    created_at: strawberry.auto
    end_date: strawberry.auto


class Product(ProductBaseType):
    product_blocks: list[ProductBlockType]
    fixed_inputs: list[FixedInputType]
    # TODO(alex)
    # workflows: list[Workflow]


@strawberry.input
class ProductInputType:
    product_blocks: list[ProductBlockType] | None
    fixed_inputs: list[FixedInputType] | None