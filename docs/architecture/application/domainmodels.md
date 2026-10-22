---
# tutorial | how-to | reference | explanation | mixed
diataxis: mixed
reviewed: true
---

# Domain Models
<!-- diataxis: explanation -->

Domain Models are designed to help the developer manage complex subscription models and interact with the objects in a
user-friendly way. They leverage [Pydantic models][pydantic-models] with some extra sauce to, among other things,
dynamically cast string values from the database to their correct type in Python at runtime.

## Why do we need them?
<!-- diataxis: explanation -->

Some Domain Model benefits are:

- Strict MyPy typing and validation in models
- Type Safe serialization to and from the database
- Subscription lifecycle transition enforcement
- Hierarchy enforcement
- Customer Facing resources vs resource facing resources <!-- TODO document this -->

When implementing domain models it is possible to link all resources together as they are nodes in a graph through the
relations defined in the domain models.

### Type Safety during serialization
<!-- diataxis: explanation -->

Logic errors that depend on type evaluations/comparisons are prevented by using domain models to serialize
database objects. This has a number of benefits as it saves the user the effort of casting the database result
to the correct type and allows the developer to be more type safe whilst developing.

#### Example
<!-- diataxis: explanation -->

!!! example
    The main reason for developing domain models was to make sure bugs like this occurred less.

    ##### Pre domain models

    ```python
    >>> some_subscription_instance_value = SubscriptionInstanceValueTable.get("ID")
    >>> instance_value_from_db = some_subscription_instance_value.value
    >>> instance_value_from_db
    "False"
    >>> if instance_value_from_db:
    ...    print("true")
    ... else:
    ...    print("false")
    "true"
    ```

    ##### Post domain models
    ```python
    >>> some_subscription_instance_value = SubscriptionInstanceValueTable.get("ID")
    >>> instance_value_from_db = some_subscription_instance_value.value
    >>> type(instance_value_from_db)
    <class str>
    >>>
    >>> subscription_model = SubscriptionModel.from_subscription("ID")
    >>> type(subscription_model.product_block.instance_from_db)
    <class bool>
    >>>
    >>> subscription_model.product_block.instance_from_db
    False
    >>>
    >>> if subscription_model.product_block.instance_from_db:
    ...    print("true")
    ... else:
    ...    print("false")
    "false"
    ```

### Lifecycle transitions
<!-- diataxis: explanation -->

When transitioning from `Initial` -> `Provisioning` -> `Active` -> `Terminated` in the Subscription Lifecycle
the domain model definitions make sure that all resource types and product blocks are assigned correctly. Typically,
the `Initial` status is less strict compared to the `Active` lifecycle. When assigning product blocks from other
subscriptions as dependent on a product block from the subscription that is being modified, the domain model respects
Subscription boundaries and do not update variables and resources in the related Subscription product block.

<!-- TODO explain what the 'domain model' is, link to reference-doc page of DomainModel class -->

### Enforcing Hierarchy
<!-- diataxis: explanation -->

When defining and modeling products it's often necessary to model resources that are in use by or dependent on other
product blocks. A product block of a subscription can also be dependent on a product block from another subscription.
This way a hierarchy of product blocks from all subscriptions can be built where the ownership of any product block is
determined by the subscription it belongs to.

#### Example
<!-- diataxis: explanation -->

We will describe some practical examples to explain how you can deal with complex customer requirements, and how to
layer subscriptions to represent a complex portfolio of network services.

1. Consider the relation between a Node and a Port: When you create Node and Port subscriptions. You should not be
   allowed to Terminate the Node subscription when the Port subscriptions are still being used by customers.

2. Consider a scenario for networking with a layer 2 circuit, one needs at least two interfaces and VLAN configuration
   to create the circuit. The interfaces may be owned by different customers than the owner of the circuit. Typically
   we assign a subscription to a customer which contains the interface resource. That interface resource is then used
   again in the circuit subscription, as a resource.

## Design examples
<!-- diataxis: mixed -->

### Product Block Model
<!-- diataxis: explanation -->

Product block models are reusable Pydantic classes that enable the user to reuse product blocks in multiple Products.
They are defined in lifecycle state and can be setup to be very restrictive or less restrictive. The orchestrator
supports hierarchy in the way product block models reference each other. In other words, a product block model, may have
a property that references one or more other product block models.

!!! info
    A Product Block should be modeled as though it is a resource that can be re-used in multiple products.
    In networking the analogy would be: A physical interface may be used in a Layer 2 service and Layer 3 service.
    It is then not necessary to define two different physical interface types.

#### Product Block Model - Inactive
<!-- diataxis: explanation -->

```python hl_lines="1 4"
class ServicePortBlockInactive(ProductBlockModel, product_block_name="Service Port"):
    """Object model for a SN8 Service Port product block."""

    nso_service_id: Optional[UUID] = None
    port_mode: Optional[PortMode] = None
    lldp: Optional[bool] = None
    ims_circuit_id: Optional[int] = None
    auto_negotiation: Optional[bool] = None
    node: Optional[NodeProductBlock] = None

```

As you can see in this model we define it as an Inactive Class.

The first highlighted line shows that parameter `product_block_name` provides the name of the product block the way it
is registered in the database.

The second highlighted line is a variable in the class.
It references a [`resource_type`](../../reference-docs/domain-models/model-attributes.md#resource-types) in the
database, and annotates that its runtime type is UUID.
It is also `Optional`, just like all other resource types in this class.

It is good practice to be least restrictive in the `Initial` phase of the Subscription lifecycle.
This allows constructing the empty initial Subscription model and extending it with inputs from the user or 
by progressing through workflow steps.

#### Product Block Model - Provisioning
<!-- diataxis: explanation -->

```python hl_lines="1-3 6"
class ServicePortBlockProvisioning(
    ServicePortBlockInactive , lifecycle=[SubscriptionLifecycle.PROVISIONING]
):
    """Object model for a SN8 Service Port product block in active state."""

    nso_service_id: UUID
    port_mode: PortMode
    lldp: bool
    ims_circuit_id: Optional[int] = None
    auto_negotiation: Optional[bool] = None
    node: NodeProductBlock
```

This model defines the `Provisioning` phase of the Subscription lifecycle. 
You can see that the class extends from the Inactive class and that it repeats all defined resource types.

You can also see that several resource types are no longer `Optional`. 
This means that the model will raise a `ValidationError` when attempting to store it without all required values.

Defining a Provisioning version of a product block is a way to ensure that a minimum set of information is present 
before proceeding with steps that, for example, provision other systems.

!!! Tip
    The stricter you are in defining your product block models the more you are able to leverage the built-in validation
    of `Pydantic`.

#### Product Block Model - Active
<!-- diataxis: explanation -->

```python hl_lines="1 4-9"
class ServicePortBlock(ServicePortBlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    """Object model for a SN8 Service Port product block in active state."""

    nso_service_id: UUID
    port_mode: PortMode
    lldp: bool
    ims_circuit_id: int
    auto_negotiation: Optional[bool] = None
    node: NodeProductBlock
```

The model is now defined in its most strict form; the `Active` phase of the Subscription lifecycle.
This product block requires almost all resource types to be provided except for `auto_negotiation`.

An Active version of a product block indicates that its configuration has been used to successfully provision other
system(s) and that it now stores references to those resources.

!!! Tip
    While you could rely on inheritance, we recommend to be explicit and always repeat resource types in each lifecycle.
    In our experience, the added "duplication" is an acceptable cost to pay because it forces you to consider how
    adding or changing a resource type in one lifecycle impacts the next lifecycle.

### Product Model
<!-- diataxis: explanation -->

Product models are very similar to Product Block Models in that they adhere to the same principles as explained above.
The Product model also contains a Product Block model which is referred to as the **root** Product Block.

One difference with Product Block models is that Product models create `Subscriptions` in the database.
Additionally, instead of dynamic resource types they contain 
[**fixed inputs**](../../reference-docs/domain-models/model-attributes.md#fixed-inputs).

The below example shows a Product model definition for each Subscription lifecycle.

=== "Inactive"

    ```python hl_lines="2 5 7"
    class ServicePortInactive(
        SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.INITIAL]
    ):
        domain: Domain
        port_speed: PortSpeed
    
        port: Optional[ServicePortBlockInactive] = None
    ```

=== "Provisioning"

    ```python hl_lines="7"
    class ServicePortProvisioning(
        ServicePortInitial, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        domain: Domain
        port_speed: PortSpeed

        port: ServicePortBlockProvisioning
    ```

=== "Active"

    ```python hl_lines="7"
    class ServicePort(
        ServicePortProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        domain: Domain
        port_speed: PortSpeed

        port: ServicePortBlock
    ```

On the **Inactive** tab, the second highlighted line shows a fixed input called `port_speed`.
This value is both limited to a range of predefined values and immutable once the Subscription is created. 

The last highlighted line `port` is the root product block which uses the `ServicePortBlockInactive` type of the same
lifecycle.

You can click through the tabs to observe how the Product definition changes depending on the lifecycle.
For example, the `port` property changes to the Product Block that corresponds to the `PROVISIONING` and `ACTIVE`
lifecycle.


!!! Tip
    While it is possible to use multiple Product Block models in your Product model, it is recommended to use one
    root Product Block.

### Advanced Use Cases
<!-- diataxis: mixed -->
<!-- TODO unmix: move 'Crossing the subscription boundary' under 'Enforcing Hierarchy', move 'Union types' to product-types.md (e.g. "Supported field annotations"), then drop this heading -->

#### Crossing the subscription boundary
<!-- diataxis: explanation -->

As mentioned before an advanced use case would be to use `ProductBlockModels` from other Subscriptions.

!!! Example
    ```python
    >>> first_service_port = ServicePort.from_subscription(subscription_id="ID")
    >>> first_service_port.customer_id
    "Y"
    >>>
    >>> second_service_port = ServicePort.from_product(product_id="ID", customer_id="ID")
    >>> second_service_port.port = first_service_port.port
    >>> second_service_port.save()
    >>>
    >>> second_service_port.port.subscription == first_service_port.subscription
    True
    >>>
    >>> second_service_port.port.subscription == second_service_port.subscription
    False
    ```

This is valid use of the domain models. The code will detect that `port` is part of `first_service_port` and respect
ownership. It basically will treat it as a read-only property.

#### Union types
<!-- diataxis: reference -->

There may also be a case where a user would like to define two different types to a `ProductBlockModel` property.
This can be achieved by using the `Union` type decorator.

```python hl_lines="4"
class ServicePort(ServicePortProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    domain: Domain
    port_speed: PortSpeed
    port: Union[ServicePortBlock, DifferentServicePortBlock]
```

<!-- link definitions -->
[pydantic-models]: https://pydantic.dev/docs/validation/latest/concepts/models/
