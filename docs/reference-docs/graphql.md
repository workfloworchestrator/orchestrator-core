# GraphQL documentation

The `orchestrator-core` comes with a graphql interface that can to be registered after you create your OrchestratorApp.
If you add it after registering your `SUBSCRIPTION_MODEL_REGISTRY` it will automatically create graphql types for them.

example:

```python
app = OrchestratorCore(base_settings=AppSettings())
# register SUBSCRIPTION_MODEL_REGISTRY
app.register_graphql()
```

## Extending the Query and Mutation

You are not able to remove resolvers from a Query, so we split the Query into 2 and merged them back for a default Query.
Our usecase for this is that we use an external graphql source as our customers root.

- `OrchestratorQuery` all resolvers except for customers.
- `CustomerQuery` only has `customers` resolver.
- `Query` Merges of `OrchestratorQuery` and `CustomerQuery` and serves as the default.

This is an basic example of how to extend the query.
You can do the same to extend Mutation.

```python
from orchestrator.graphql import Query, Mutation, OrchestratorQuery


# Queries
def resolve_new(info) -> str:
    return "resolve new..."


# with customers.
@strawberry.federation.type(description="Orchestrator queries")
class NewQuery(Query):
    other_processes: Connection[ProcessType] = authenticated_field(
        resolver=resolve_processes,
        description="resolve_processes used for another field",
    )
    new: str = strawberry.field(resolve_new, description="new resolver")

# without customers.
@strawberry.federation.type(description="Orchestrator queries")
class NewQueryWithoutCustomers(OrchestratorQuery):
    other_processes: Connection[ProcessType] = authenticated_field(
        resolver=resolve_processes,
        description="resolve_processes used for another field",
    )
    new: str = strawberry.field(resolve_new, description="new resolver")


app = OrchestratorCore(base_settings=AppSettings())
# register SUBSCRIPTION_MODEL_REGISTRY
app.register_graphql(query=NewQuery)
```

## Adding federated types to the graphql

federation introduction: https://strawberry.rocks/docs/federation/introduction

Within a federation, it is possible to add orchestrator data to graphql types from other sources by extending the `DEFAULT_GRAPHL_MODELS` dictionary with your own federated classes and adding them as parameter to `app.register_graphql(graphql_models={})`. Here is an example for when instead of overriding the customers resolver, you instead use a different graphql source (know that not storing any customer data in the orchestator will make filtering and sorting unavailable and very tricky to implement):

```python
import strawberry
from sqlalchemy import select

from oauth2_lib.strawberry import authenticated_field
from orchestrator.db import db
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.schemas.subscription import SubscriptionInterface
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo


@strawberry.federation.type(description="Customer", keys=["customer_id"])
class Customer:
    customer_id: str

    @classmethod
    async def resolve_reference(cls, customer_id: str) -> "Customer":  # noqa: N803
        return Customer(customer_id=customer_id)

    @authenticated_field(description="Returns subscriptions of a customer")  # type: ignore
    async def subscriptions(
        self,
        info: OrchestratorInfo,
        filter_by: list[GraphqlFilter] | None = None,
        sort_by: list[GraphqlSort] | None = None,
        first: int = 10,
        after: int = 0,
    ) -> Connection[SubscriptionInterface]:
        from orchestrator.graphql.resolvers.subscription import resolve_subscriptions

        filter_by_customer_id = (filter_by or []) + [GraphqlFilter(field="customerId", value=str(self.uuid))]  # type: ignore
        return await resolve_subscriptions(info, filter_by_customer_id, sort_by, first, after)

UPDATED_GRAPHQL_MODELS = DEFAULT_GRAPHQL_MODELS | {
    "Customer": Customer,
}

app.register_graphql(query=OrchestratorQuery, graphql_models=UPDATED_GRAPHQL_MODELS)
```

Types that are added in this way but aren't used in a resolver, will be viewable outside of a federation inside the types in the graphql ui interface.
Adding product or product block strawberry types to the `graphql_models` will skip their generation inside `register_domain_models`. More info [here](#domain-models-auto-registration-for-graphql)

## Add Json schema for metadata

The metadata in a subscription is completely unrestricted and can have anything.
This functionality is to make metadata descriptive in a `__schema__` for the frontend to be able to render the metadata and know what to do with typing.

example how to update the `__schema__`:

```python
from orchestrator.graphql.schemas.subscription import MetadataDict


class Metadata(BaseModel):
    some_metadata_prop: list[str]


MetadataDict.update({"metadata": Metadata})
```

This will result in json schema:

```Json
{
    "title": "Metadata",
    "type": "object",
    "properties": {
        "some_metadata_prop": {
            "title": "Some Metadata Prop",
            "type": "array",
            "items": {
                "type": "string"
            }
        }
    },
    "required": [
        "some_metadata_prop"
    ]
}
```

## Domain Models Auto Registration for GraphQL

When using the `app.register_graphql()` function, all products in the `SUBSCRIPTION_MODEL_REGISTRY` will be automatically converted into GraphQL types.
You are able to turn this off with `app.register_graphql(register_models=False)`, but then you can only query fields from the default `SubscriptionModel`.
The registration process iterates through the list, starting from the deepest product block and working its way back up to the product level.

However, there is a potential issue when dealing with a `ProductBlock` that references itself, as it could lead to an error expecting the `ProductBlock` type to exist.

Here is an example of the expected error with a self referenced `ProductBlock`:

```
strawberry.experimental.pydantic.exceptions.UnregisteredTypeException: Cannot find a Strawberry Type for <class 'products.product_blocks.product_block_file.ProductBlock'> did you forget to register it?
```

To handle this situation, you must manually create the GraphQL type for that `ProductBlock` and add it to the `DEFAULT_GRAPHQL_MODELS` list.

Here's an example of how to do it:

```python
# product_block_file.py
import strawberry
from typing import Annotated
from app.product_blocks import ProductBlock
from orchestrator.graphql import DEFAULT_GRAPHQL_MODELS


# It is necessary to use pydantic type, so that other product blocks can recognize it when typing to GraphQL.
@strawberry.experimental.pydantic.type(model=ProductBlock)
class ProductBlockGraphql:
    name: strawberry.auto
    self_reference_block: Annotated[
        "ProductBlockGraphql", strawberry.lazy(".product_block_file")
    ] | None = None
    ...


# Add the ProductBlockGraphql type to GRAPHQL_MODELS, which skips its auto-register and used for products or product blocks dependant on it.
UPDATED_GRAPHQL_MODELS = DEFAULT_GRAPHQL_MODELS | {
    "ProductBlockGraphql": ProductBlockGraphql,
}

app.register_graphql(query=OrchestratorQuery, graphql_models=UPDATED_GRAPHQL_MODELS)
```

By following this example, you can effectively create the necessary GraphQL type for `ProductBlock` and ensure proper registration with `app.register_graphql()`. This will help you avoid any `Cannot find a Strawberry Type` scenarios and enable smooth integration of domain models with GraphQL.

### Scalars for Auto Registration

When working with special types such as `VlanRanges` or `IPv4Interface` in the core module, scalar types are essential for the auto registration process.
Scalar types enable smooth integration of these special types into the GraphQL schema, They need to be initialized and can be added with a dict to `app.register_graphql(scalar_overrides={})`.

Here's an example of how to add a new scalar:

```python
import strawberry
from typing import NewType
from orchestrator.graphql import SCALAR_OVERRIDES

VlanRangesType = strawberry.scalar(
    NewType("VlanRangesType", str),
    description="Represent the Orchestrator VlanRanges data type",
    serialize=lambda v: v.to_list_of_tuples(),
    parse_value=lambda v: v,
)

# Add the scalar to the SCALAR_OVERRIDES dictionary, with the type in the product block as the key and the scalar as the value
UPDATED_SCALAR_OVERRIDES = SCALAR_OVERRIDES | {
    VlanRanges: VlanRangesType,
}

app.register_graphql(other_params..., scalar_overrides=UPDATED_SCALAR_OVERRIDES)
```

You can find more examples of scalar usage in the `orchestrator/graphql/types.py` file.
For additional information on Scalars, please refer to the Strawberry documentation on Scalars: https://strawberry.rocks/docs/types/scalars.

By using scalar types for auto registration, you can seamlessly incorporate special types into your GraphQL schema, making it easier to work with complex data in the Orchestrator application.


### Federating with Autogenerated Types

To enable federation, set the `FEDERATION_ENABLED` environment variable to `True`.

!!! info
    The dockerized [example-orchestrator](../getting-started/docker.md) contains a working Federation setup that demonstrates how the below works in practice.

Federation allows you to federate with subscriptions using the `subscriptionId` and with product blocks inside the subscription by utilizing any property that includes `_id` in its name.

Below is an example of a GraphQL app that extends the `SubscriptionInterface`:

```python
from typing import Any

import strawberry
from starlette.applications import Starlette
from starlette.routing import Route
from strawberry.asgi import GraphQL
from uuid import UUID


@strawberry.federation.interface_object(keys=["subscriptionId"])
class SubscriptionInterface:
    subscription_id: UUID
    new_value: str

    @classmethod
    async def resolve_reference(cls, **data: Any) -> "SubscriptionInterface":
        if not (subscription_id := data.get("subscriptionId")):
            raise ValueError(
                f"Need 'subscriptionId' to resolve reference. Found keys: {list(data.keys())}"
            )

        value = new_value_resolver(subscription_id)
        return SubscriptionInterface(subscription_id=subscription_id, new_value=value)


@strawberry.type
class Query:
    hi: str = strawberry.field(resolver=lambda: "query for other graphql")


# Add `SubscriptionInterface` in types array.
schema = strawberry.federation.Schema(
    query=Query,
    types=[SubscriptionInterface],
    enable_federation_2=True,
)

app = Starlette(debug=True, routes=[Route("/", GraphQL(schema, graphiql=True))])
```

To run this example, execute the following command:

```bash
uvicorn app:app --port 4001 --host 0.0.0.0 --reload
```

In the `supergraph.yaml` file, you can federate the GraphQL endpoints together as shown below:

```yaml
federation_version: 2
subgraphs:
  orchestrator:
    routing_url: https://orchestrator-graphql-endpoint
    schema:
      subgraph_url: https://orchestrator-graphql-endpoint
  new_graphql:
    routing_url: http://localhost:4001
    schema:
      subgraph_url: http://localhost:4001
```

When both GraphQL endpoints are available, you can compose the supergraph schema using the following command:

```bash
rover supergraph compose --config ./supergraph.yaml > supergraph-schema.graphql
```

The command will return errors if incorrect keys or other issues are present.
Then, you can run the federation with the following command:

```bash
./router --supergraph supergraph-schema.graphql
```

Now you can query the endpoint to obtain `newValue` from all subscriptions using the payload below:

```json
{
    "rationName":  "ExampleQuery",
    "query": "query ExampleQuery {\n  subscriptions {\n    page {\n      newValue\n    }\n  }\n}\n",
    "variables": {}
}
```

#### Federating with Specific Subscriptions

To federate with specific subscriptions, you need to make a few changes. Here's an example of a specific subscription:

```python
# `type` instead of `interface_object` and name the class exactly the same as the one in orchestrator.
@strawberry.federation.type(keys=["subscriptionId"])
class YourProductSubscription:
    subscription_id: UUID
    new_value: str

    @classmethod
    async def resolve_reference(cls, **data: Any) -> "SubscriptionInterface":
        if not (subscription_id := data.get("subscriptionId")):
            raise ValueError(
                f"Need 'subscriptionId' to resolve reference. Found keys: {list(data.keys())}"
            )

        value = new_value_resolver(subscription_id)
        return SubscriptionInterface(subscription_id=subscription_id, new_value=value)
```

#### Federating with Specific Subscription Product Blocks

You can also federate a ProductBlock. In this case, the `subscriptionInstanceId` can be replaced with any product block property containing `Id`:

```python
@strawberry.federation.interface_object(keys=["subscriptionInstanceId"])
class YourProductBlock:
    subscription_instance_id: UUID
    new_value: str

    @classmethod
    async def resolve_reference(cls, **data: Any) -> "YourProductBlock":
        if not (subscription_id := data.get("subscriptionInstanceId")):
            raise ValueError(
                f"Need 'subscriptionInstanceId' to resolve reference. Found keys: {list(data.keys())}"
            )

        value = "new value"
        return YourProductBlock(subscription_id=subscription_id, new_value="new value")
```

By following these examples, you can effectively federate autogenerated types (`subscriptions` and `product blocks`) enabling seamless integration across multiple GraphQL endpoints.

### Usage of USE_PYDANTIC_ALIAS_MODEL_MAPPING

`USE_PYDANTIC_ALIAS_MODEL_MAPPING` is a mapping to prevent pydantic field alias from being used as field names when creating strawberry types in the domain model autoregistration.
Our usecase for this is that functions decorated with pydantics `@computed_field` and `@property` in domain models are not converted to strawberry fields inside the strawberry types.
to add the function properties, we use a aliased pydantic field:

```python
class ExampleProductInactive(SubscriptionModel, is_base=True):
    # this aliased property is used to add `property_example` as strawberry field.
    # you need a default it the value can't be `None` since it doesn't directly add the return value of property_example
    aliased_property_example: Field(alias="property_example", default="")

    # this computed property function does not get converted into the strawberry type.
    @computed_field  # type: ignore[misc]
    @property
    def property_example(self) -> str:
        return "example"


class ExampleProductProvisioning(
    ExampleProductInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
):
    pass


class ExampleProduct(ExampleProductInactive, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    pass
```

The problem with this is that strawberry automatically uses the alias name and doesn't camelcase it so the strawberry field becomes `property_example`.
To fix it and have camelcasing, we can prevent aliases from being used in strawberry.type using the created mapping `USE_PYDANTIC_ALIAS_MODEL_MAPPING`:

```python
from orchestrator.graphql.autoregistration import USE_PYDANTIC_ALIAS_MODEL_MAPPING

USE_PYDANTIC_ALIAS_MODEL_MAPPING.update({"ExampleProductSubscription": False})
```

which would now give us a strawberry field `aliasedPropertyExample`.
To name it `propertyExample` you can't override the function property name and have two choices.

1. camelcase the aliased property:
   ```python
   class ExampleProductInactive(SubscriptionModel, is_base=True):
       # this aliased property is used to add `property_example` as strawberry field.
       propertyExample: Field(alias="property_example")
   ```

2. rename the property function and name the aliased field correctly, when accessing outside of the graphql field, you do need to use `computed_property_example` instead of `property_example`:
   ```python
   class ExampleProductInactive(SubscriptionModel, is_base=True):
       # this aliased property is used to add `property_example` as strawberry field.
       property_example: Field(alias="computed_property_example")

       # this computed property function does not get converted into the strawberry type.
       @computed_field  # type: ignore[misc]
       @property
       def computed_property_example(self) -> str:
           return "example"
   ```

## Overriding Types

Overriding strawberry types can be achieved through various methods. One less desirable approach involves extending classes using class inheritance.
However, this method becomes cumbersome when updating a single class, as it necessitates updating all associated types and their corresponding resolvers, essentially impacting the entire structure.

For instance, consider the scenario of overriding the `CustomerType`. you would need to update the related `SubscriptionInterface`, `ProcessType` and their respective resolvers. due to these modifications, all their related types and resolvers would also require updates, resulting in a tedious and error-prone process.

To enhance the override process, we created a helper function `override_class` to override fields. It takes the base class as well as a list of fields that will replace their counterparts within the class or add new fields.

It's worth noting that `SubscriptionInterface` poses a unique challenge due to its auto-generated types. The issue arises from the fact that the models inherited from `SubscriptionInterface` do not automatically update. This can be addressed by utilizing the `override_class` function and incorporating the returned class into the `app.register_graphql` function. This ensures that the updated class, with overridden fields, becomes the basis for generating the auto-generated models.

```python
# Define a custom subscription interface using the `override_class` function, incorporating specified override fields.
custom_subscription_interface = override_class(SubscriptionInterface, override_fields)

# Register the customized subscription interface when setting up GraphQL in your application.
app.register_graphql(subscription_interface=custom_subscription_interface)
```

quick example (for more indebt check customerType override):

```python
import strawberry
from orchestrator.graphql.utils.override_class import override_class


# Define a strawberry type representing an example entity
@strawberry.type()
class ExampleType:
    @strawberry.field(description="Existing field")  # type: ignore
    def existing(self) -> int:
        return 1


# Define a strawberry type for example queries
@strawberry.type(description="Example queries")
class Query:
    example: ExampleType = strawberry.field(resolver=lambda: ExampleType())


# Create a resolver for updating the existing field
async def update_existing_resolver() -> str:
    return "updated to new type"


# Create a strawberry field with the resolver for the existing field
existing_field = strawberry.field(resolver=update_existing_resolver, description="update existing field")  # type: ignore
# Assign a new name to the strawberry field; this name will override the existing field in the class
existing_field.name = "existing"


# Create a new field with a resolver
async def new_resolver() -> int:
    return 1


new_field = strawberry.field(resolver=new_resolver, description="a new field")  # type: ignore
# Assign a name that is not present in the class yet
new_field.name = "new"

# Use the override_class function to replace fields in the ExampleType
override_class(ExampleType, [new_field, existing_field])
```

### Overriding CustomerType and Resolvers

Within the orchestrator core, there exists a base `CustomerType` designed to provide a default customer, allowing for the customization of data through environment variables.
This approach minimizes the necessity for everyone to implement custom customer logic.

Below, I present an example illustrating how to override the `CustomerType` and its associated resolvers.

#### CustomerType Override

Here's a generic override for the `CustomerType` that introduces a new `subscriptions` relation:

```python
from typing import Annotated

import strawberry

from oauth2_lib.strawberry import authenticated_field
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.schemas.customer import CustomerType
from orchestrator.graphql.schemas.subscription import (
    SubscriptionInterface,
)  # noqa: F401
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils.override_class import override_class

# Type annotation for better readability rather than having this directly as a return type
SubscriptionInterfaceType = Connection[
    Annotated[
        "SubscriptionInterface",
        strawberry.lazy("orchestrator.graphql.schemas.subscription"),
    ]
]


# Resolver for fetching subscriptions of a customer
async def resolve_subscriptions(
    root: CustomerType,
    info: OrchestratorInfo,
    filter_by: list[GraphqlFilter] | None = None,
    sort_by: list[GraphqlSort] | None = None,
    first: int = 10,
    after: int = 0,
) -> SubscriptionInterfaceType:
    from orchestrator.graphql.resolvers.subscription import resolve_subscriptions

    # Include the filter for the customer ID; since 'customerId' exists in the subscription, filtering updates are not required.
    filter_by_customer_id = (filter_by or []) + [GraphqlFilter(field="customerId", value=str(root.customer_id))]  # type: ignore
    return await resolve_subscriptions(
        info, filter_by_customer_id, sort_by, first, after
    )


# Create an authenticated field for customer subscriptions
customer_subscriptions_field = authenticated_field(
    resolver=resolve_subscriptions, description="Returns subscriptions of a customer"
)
# Assign a new name to the strawberry field; this name will add the 'subscriptions' field in the class
customer_subscriptions_field.name = "subscriptions"

# Override the CustomerType with the new 'subscriptions' field
override_class(CustomerType, [customer_subscriptions_field])
```

#### CustomerType Resolver Override

In this example code, we introduce a resolver override for the `CustomerType`. The scenario involves a supplementary `CustomerTable` in the database, encompassing the default values of `CustomerType`—namely, `customer_id`, `fullname`, and `shortcode`.

```python
import structlog
from sqlalchemy import func, select

from orchestrator.db import db
from orchestrator.db.filters import Filter
from orchestrator.db.range.range import apply_range_to_statement
from orchestrator.db.sorting import Sort
from orchestrator.graphql.pagination import Connection
from orchestrator.graphql.resolvers.helpers import rows_from_statement
from orchestrator.graphql.schemas.customer import CustomerType
from orchestrator.graphql.types import GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.graphql.utils.create_resolver_error_handler import (
    create_resolver_error_handler,
)
from orchestrator.graphql.utils.to_graphql_result_page import to_graphql_result_page
from orchestrator.utils.search_query import create_sqlalchemy_select
from your_customer_table_location.db.models import CustomerTable

# # Import custom sorting and filtering modules used with `sort_by` and `filter_by`.
# from sort_loc import sort_customers, sort_customers_fields
# from filter_loc import filter_customers, filter_customers_fields

logger = structlog.get_logger(__name__)


# Queries
def resolve_customers(
    info: OrchestratorInfo,
    filter_by: list[GraphqlFilter] | None = None,
    sort_by: list[GraphqlSort] | None = None,
    first: int = 10,
    after: int = 0,
    query: str | None = None,
) -> Connection[CustomerType]:
    # ---- DEFAULT RESOLVER LOGIC ----
    _error_handler = create_resolver_error_handler(info)

    pydantic_filter_by: list[Filter] = [item.to_pydantic() for item in filter_by] if filter_by else []  # type: ignore
    pydantic_sort_by: list[Sort] = [item.to_pydantic() for item in sort_by] if sort_by else []  # type: ignore
    logger.debug(
        "resolve_customers() called",
        range=[after, after + first],
        sort=pydantic_sort_by,
        filter=pydantic_filter_by,
    )
    # ---- END OF DEFAULT RESOLVER LOGIC ----

    select_stmt = select(CustomerTable)

    # # Include custom filtering logic if imported
    # select_stmt = filter_customers(select_stmt, pydantic_filter_by, _error_handler)

    if query is not None:
        stmt = create_sqlalchemy_select(
            select_stmt,
            query,
            mappings={},
            base_table=CustomerTable,
            join_key=CustomerTable.customer_id,
        )
    else:
        stmt = select_stmt

    # # Include custom sorting logic if imported
    # stmt = sort_customers(stmt, pydantic_sort_by, _error_handler)

    # ---- DEFAULT RESOLVER LOGIC ----
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = apply_range_to_statement(stmt, after, after + first + 1)

    customers = rows_from_statement(stmt, CustomerTable)
    graphql_customers = [
        CustomerType(
            customer_id=c.customer_id, fullname=c.fullname, shortcode=c.shortcode
        )
        for c in customers
    ]
    return to_graphql_result_page(
        graphql_customers,
        first,
        after,
        total,
        sort_customers_fields,
        filter_customers_fields,
    )
    # ---- END OF DEFAULT RESOLVER LOGIC ----
```

#### CustomerType Related Type Overrides

Having overridden the `customer_resolver` and added the `subscriptions` field to the `CustomerType`, the final step involves updating the related strawberry types, namely `SubscriptionInterface` and `ProcessType`.

For both types, the `customer_id` is at the root, allowing us to create a generic override resolver for both.
As we modify `SubscriptionInterface`, it's essential to utilize the returned type (stored in the `custom_subscription_interface` variable) when registering GraphQL in the application using `app.register_graphql(subscription_interface=custom_subscription_interface)`.

```python
async def resolve_customer(root: CustomerType) -> CustomerType:
    stmt = select(CustomerTable).where(CustomerTable.customer_id == root.customer_id)

    if not (customer := db.session.execute(stmt).scalars().first()):
        return CustomerType(
            customer_id=root.customer_id, fullname="missing", shortcode="missing"
        )

    return CustomerType(
        customer_id=customer.customer_id,
        fullname=customer.fullname,
        shortcode=customer.shortcode,
    )


# Create a strawberry field with the resolver for the customer field
customer_field = strawberry.field(resolver=resolve_customer, description="Returns customer of a subscription")  # type: ignore
# Assign a new name to the strawberry field; this name will add the 'customer' field in the class
customer_field.name = "customer"

# Override the SubscriptionInterface and ProcessType with the new 'customer' field
override_class(ProcessType, [customer_field])
custom_subscription_interface = override_class(SubscriptionInterface, [customer_field])
```
