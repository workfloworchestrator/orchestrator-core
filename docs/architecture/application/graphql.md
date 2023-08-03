# GraphQL documentation

OrchestratorCore comes with a graphql interface that can to be registered after you create your OrchestratorApp.
If you add it after registering your `SUBSCRIPTION_MODEL_REGISTRY` it will automatically create graphql types for them.

example:

```python
app = OrchestratorCore(base_settings=AppSettings())
# register SUBSCRIPTION_MODEL_REGISTRY
app.register_graphql()
```

## Extending the Query and Mutation

This is an basic example of how to extend the query.
You can do the same to extend Mutation.

```python
from orchestrator.graphql import Query, Mutation


# Queries
def resolve_new(info) -> str:
    return "resolve new..."


@strawberry.federation.type(description="Orchestrator queries")
class NewQuery(Query):
    other_processes: Connection[ProcessType] = authenticated_field(
        resolver=resolve_processes,
        description="resolve_processes used for another field",
    )
    new: str = strawberry.field(resolve_new, description="new resolver")


app = OrchestratorCore(base_settings=AppSettings())
# register SUBSCRIPTION_MODEL_REGISTRY
app.register_graphql(query=NewQuery)
```

## Domain Models Auto Registration for GraphQL

When using the register_graphql function, all products in the SUBSCRIPTION_MODEL_REGISTRY will be automatically converted into GraphQL types.
The registration process iterates through the list, starting from the deepest product block and working its way back up to the product level.

However, there is a potential issue when dealing with a ProductBlock that references itself, as it can lead to an infinite loop.
To handle this situation, you must manually create the GraphQL type for that ProductBlock and add it to the GRAPHQL_MODELS list.

Here's an example of how to do it:

```python
import strawberry
from typing import Annotated
from app.product_blocks import ProductBlock
from orchestrator.graphql import GRAPHQL_MODELS


# It is necessary to use pydantic type, so that other product blocks can recognize it when typing to GraphQL.
@strawberry.experimental.pydantic.type(model=ProductBlock)
class ProductBlockGraphql:
    name: strawberry.auto
    self_refrence_block: Annotated[
        "ProductBlockGraphql", strawberry.lazy(".product_block_file")
    ] | None = None
    ...


# Add the ProductBlockGraphql type to GRAPHQL_MODELS, which is used in auto-registration for already created product blocks.
GRAPHQL_MODELS.update({"ProductBlockGraphql": ProductBlockGraphql})
```

By following this example, you can effectively create the necessary GraphQL type for ProductBlock and ensure proper registration with register_graphql. This will help you avoid any infinite loop scenarios and enable smooth integration of domain models with GraphQL.

### Scalars for Auto Registration

When working with special types such as VlanRanges or IPv4Interface in the core module, scalar types are essential for the auto registration process.
Scalar types enable smooth integration of these special types into the GraphQL schema.

Here's an example of how to add a new scalar:

```python
import strawberry
from typing import NewType
from orchestrator.graphql import SCALAR_OVERRIDESs

VlanRangesType = strawberry.scalar(
    NewType("VlanRangesType", str),
    description="Represent the Orchestrator VlanRanges data type",
    serialize=lambda v: v.to_list_of_tuples(),
    parse_value=lambda v: v,
)

# Add the scalar to the SCALAR_OVERRIDES dictionary, with the type in the product block as the key and the scalar as the value
SCALAR_OVERRIDES = {
    VlanRanges: VlanRangesType,
}
```

You can find more examples of scalar usage in the `orchestrator-core/orchestrator/graphql/types.py` file.
For additional information on Scalars, please refer to the Strawberry documentation on Scalars: https://strawberry.rocks/docs/types/scalars.

By using scalar types for auto registration, you can seamlessly incorporate special types into your GraphQL schema, making it easier to work with complex data in the Orchestrator application.
