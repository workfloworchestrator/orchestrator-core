# Workflow Steps

Workflows are what actually takes a product definition and populates your domain models. To read more about the architectural design of workflows check out [the architecture page on workflows.](../../architecture/application/workflow.md) To see more details about the types of steps that are available for use, read on to the next section.

## Step Types

::: orchestrator.core.workflow
    options:
        heading_level: 3
        members:
        - step
        - retrystep
        - inputstep
        - stepgroup
        - callbackstep
        - conditional

## Step Importance

Every step carries an `importance` value, which the orchestrator stores on each process step and exposes through the
REST and GraphQL process APIs. The orchestrator UI uses it to decide how much of each step to show in the process
detail page. The engine itself does not change its behaviour based on importance.

The value is a member of `StepImportance`: `low`, `default` or `high`. Every step is `default` unless specified,
including the built-in `Start`, `Done` and `Abort` steps.

### How the UI renders importance

The process detail page has a **Detail** selector with three levels: Minimal, Standard and Verbose. Each step is
rendered in one of three presentations depending on the selected level and the step's importance:

- **Minimal**: a single compact row with the status icon and the step name (the name can be hidden via a toggle).
- **Standard**: the regular step card with name, status and duration, collapsed.
- **Verbose**: the step card expanded, showing the state and subscription delta.

| Detail level | `high` step | `default` step | `low` step |
|--------------|-------------|----------------|------------|
| Minimal      | Standard    | Minimal        | Minimal    |
| Standard     | Verbose     | Standard       | Minimal    |
| Verbose      | Verbose     | Verbose        | Standard   |

Steps that need attention are never collapsed to minimal, regardless of importance: a running step, a suspended step
waiting for user input, and a failed step at the end of the process are shown at least as Standard. Clicking a step
expands it one presentation level and clicking an expanded step shrinks it back.

In practice: mark a step `high` when an operator should see its result without clicking (for example the step that
pushes configuration to the network), and `low` for housekeeping steps that only add noise, such as cleaning up
temporary state.

### Setting the importance

Pass it as a keyword to `@step`, `@retrystep`, `@inputstep`, `callback_step` or `step_group`:

```python
from orchestrator.core.workflow import StepImportance, step


@step("Deploy to network", importance=StepImportance.HIGH)
def deploy_to_network(subscription: SubscriptionModel) -> State:
    ...
```

For `callback_step`, importance applies to the whole group's single process step row, including while awaiting a
callback. `step_group` also accepts `importance`; its value, not its children's values, is stored on the shared row.
Steps wrapped by `conditional` or `steplens` keep the importance of the step they wrap.

Pending steps (steps not yet executed) report the importance from the step definition; executed steps report the
value that was stored when the step ran.

## Database Implications

Because a workflow is tied to a product type, this means that you will need a new database migration when adding new workflows. Thankfully, the CLI tool will help you with this! Check out the [CLI docs for `db migrate-workflows`](../cli.md#orchestrator.core.cli.database.migrate_workflows) for more information.

## Building a Step Function Signature

One important detail that is very helpful to understand is how your Step Function's python function signature is used to deserialize objects from the database into something you can use in your workflow python code. The WFO achieves this by introspecting the step function signature for the type hints you've defined and then tries to populate the appropriate objects for you. To understand the details of how this works, look at this method:

::: orchestrator.core.utils.state.inject_args
    options:
        heading_level: 3


## Reusable Workflow Steps

When designing workflows it is good practice to make steps reusable.
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

While this approach works, the switch logic (via `match` or `if isinstance()`) can become unwieldy as more product types are introduced.
This is where `@singledispatch` can help.

### Using `@singledispatch` for Cleaner Re-usability

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
