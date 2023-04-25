import strawberry

from orchestrator.graphql.schemas.fixed_input import FixedInput
from orchestrator.graphql.schemas.product_block import ProductBlock
from orchestrator.graphql.schemas.workflow import Workflow
from orchestrator.schemas.product import ProductSchema


@strawberry.experimental.pydantic.type(
    model=ProductSchema,
    fields=[
        "product_id",
        "name",
        "description",
        "product_type",
        "status",
        "tag",
        "created_at",
        "end_date",
        "product_blocks",
    ],
)
class Product:
    product_blocks: list[ProductBlock]
    fixed_inputs: list[FixedInput]
    workflows: list[Workflow]
