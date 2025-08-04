# Workflow Steps

Workflows are what actually takes a product definition and populates your domain models. To read more about the architectural design of workflows check out [the architecture page on workflows.](../../architecture/application/workflow.md) To see more details about the types of steps that are available for use, read on to the next section.

## Step Types

::: orchestrator.workflow
    options:
        heading_level: 3
        members:
        - step
        - retrystep
        - inputstep
        - stepgroup
        - callbackstep
        - conditional

## Database Implications

Because a workflow is tied to a product type, this means that you will need a new database migration when adding new workflows. Thankfully, the CLI tool will help you with this! Check out the [CLI docs for `db migrate-workflows`](../cli.md#orchestrator.cli.database.migrate_workflows) for more information.

## Building a Step Function Signature

One important detail that is very helpful to understand is how your Step Function's python function signature is used to deserialize objects from the database into something you can use in your workflow python code. The WFO achieves this by introspecting the step function signature for the type hints you've defined and then tries to populate the appropriate objects for you. To understand the details of how this works, look at this method:

::: orchestrator.utils.state.inject_args
    options:
        heading_level: 3


## Reusable Workflow Steps in Orchestrator Core

When designing workflows in Orchestrator Core, reusability is key.
With a single product definition, you can build reusable steps for both `CREATE` and `MODIFY` workflows.
For example, you may want to:

- Update a product's description using subscription properties.
- Push data to an external system via an upsert operation.

To take reusability further, Python's `@singledispatch` decorator can help abstract product-specific logic behind a common interface.
This makes your steps cleaner, easier to reuse across multiple workflows and more maintainable.


### Generic Workflow Steps

You can define a generic step when the logic should be shared across multiple workflows or products.
Here's an example of a reusable workflow step that updates an external system based on the product type:

```python
@step("Update external system")
def update_external_system(subscription: SubscriptionModel):
    match type(subscription):
        case ProductTypeOne:
            payload = create_product_type_one_payload(subscription.some_block)
        case ProductTypeTwo:
            payload = create_product_type_two_payload(subscription.some_other_block)
        case _:
            raise TypeError(f"Unsupported subscription type: {type(subscription)}")

    response = external_system_request(payload)
    return {"response": response}
```

While this approach works, the switch logic (via match or if isinstance) can become unwieldy as more product types are introduced.
This is where `@singledispatch` can help.

### Using `@singledispatch` for Cleaner Reusability

In the example above, each product requires slightly different logic for building the payload.
Rather than branching on type manually, you can delegate this responsibility to Python's `@singledispatch`.

With `@singledispatch`, you define a generic function and register specific implementations based on the type of the input model.

Benefits:

- Simplifies logic: No need for `match` or if `isinstance` checks.
- Improves maintainability: Logic is cleanly separated per product.
- Enhances extensibility: Easily add new product support with a new @register.

> Note: When using `@singledispatch` with Orchestrator models like `SubscriptionModel`, be sure to register specific lifecycle types (e.g., `ProductTypeOneProvisioning`).

Example: Single Dispatch for External System Updates (default function)

```python
from functools import singledispatch
from surf.utils.singledispatch import single_dispatch_base

@singledispatch
def update_external_system(model: SubscriptionModel) -> str:
    """
    Generic function to update an external system based on a subscription model.
    Specific implementations must be registered for each product type.

    Args:
        model: The subscription lifecycle model.

    Returns:
        A response json from the external system.

    Raises:
        TypeError: If no registered implementation is found for the model.
    """
    return single_dispatch_base(update_external_system, model)
```

Registering Implementations:

```python
@update_external_system.register
def product_one_update_external_system(model: ProductTypeOneProvisioning | ProductTypeOne) -> str:
    payload = {}  # add payload logic...
    return external_system_request(payload)


@update_external_system.register
def product_two__active_update_external_system(model: ProductTypeTwo) -> str:
    payload = {}  # add payload logic...
    return external_system_request(payload)


@update_external_system.register
def product_two_provisioning_update_external_system(model: ProductTypeTwoProvisioning) -> str:
    payload = {}  # add payload logic...
    return external_system_request(payload)
```

Now you can call `update_external_system(model)` without worrying about branching logic.
The correct function will be called based on the model's type.
