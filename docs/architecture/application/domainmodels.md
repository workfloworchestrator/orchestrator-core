# Domain Models - Why do we need them?

Domain Models are designed to help the developer manage complex subscription models and interact with the objects in a
user-friendly way. Domain models leverage the [Pydantic](https://pydantic-docs.helpmanual.io/) with some extra sauce to
dynamically cast variables from the database where they are stored as a string to their correct type in Python at runtime.

**Domain Model benefits**

- Strict MyPy typing and validation in models.
- Type Safe serialisation to and from the database
- Subscription lifecycle transition enforcement
- Hierarchy enforcement with domain models
- Customer Facing resources vs resource facing resources

When implementing domain models it is possible to link all resources together as they are nodes in a graph through the
relations defined in the domain models.

### Type Safety during serialisation
Logic errors that depend on type evaluations/comparisons are prevented by using domain models to serialise database objects.
This has a number of benefits as it saves the user the effort of casting the database result to the correct type and allows
the developer to be more `Type safe` whilst developing.

#### Example
!!! example
    The main reason for developing domain models was to make sure bugs like this occured less.
    ##### Pre domain models

    ```python
    >>> some_subscription_instance_value = SubscriptionInstanceValueTable.get("ID")
    >>> instance_value_from_db = some_subscription_instance_value.value
    >>> instance_value_from_db
    "False"
    >>> if instance_value_from_db is True:
    ...    print("True")
    ... else:
    ...    print("False")
    "True"
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
    >>> if subscription_model.product_block.instance_from_db is True:
    ...    print("True")
    ... else:
    ...    print("False")
    "False"
    ```

### Lifecycle transitions
When transitioning from `Initial` -> `Provisioning` -> `Active` -> `Terminated` in the Subscription Lifecycle
the domain model definitions make sure that all resource types and product blocks are assigned correctly. Typically
the `Initial` status is less strict compared to the `Active` lifecycle. When assigning product blocks from other
subscriptions as dependent on a product block from the subscription that is being modified, the domain-models respect
Subscription boundaries and do not update variables and resources in the related Subscription product block.

### Enforcing Hierarchy

When defining and modelling products it's often necessary to model resources
that are in use by or dependent on other product blocks. A product block of a
subscription can also be dependent on a product block from another
subscription. This way a hierarchy of product blocks from all subscriptions
can be build where the ownership of any product block is determined by the
subscription it belongs to.

#### A couple of Examples of subscription hierarchies

We will describe some practical examples to explain how you can deal with complex customers requirements, and how to
layer subscriptions to represent a complex portfolio of network services.

1. Consider the relation between a Node and a Port: When you create Node and Port subscriptions. You should not be
allowed to Terminate the Node subscriptions when the Port subscriptions are still being used by customers.

2. Consider a scenario for networking with a layer 2 circuit, one needs at least two interfaces and VLAN configuration to create
the circuit. The interfaces may be owned by different customers than the owner of the circuit. Typically we assign a
subscription to a customer which contains the interface resource. That interface resource is then used again
in the circuit subscription, as a resource.


## Code examples
#### Product Block Model
Product block models are reusable Pydantic classes that enable the user to reuse product blocks in multiple Products.
They are defined in lifecycle state and can be setup to be very restrictive or less restrictive. The orchestrator
supports hierarchy in the way product block models reference each other. In other words, a product block model, may have
a property that references one or more other product block models.

!!! info
    The Product block model should be modeled as though it is a resource that can be re-used in multiple products.
    In networking the analogy would be: A physical interface may be used in a Layer 2 service and Layer 3 service
    It is not necessary to define two different physical interface types.

##### Product Block Model - Inactive
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
As you can see in this model we define it as an Inactive Class. As parameter we pass the name of the product_block in the
database. In the second highlighted line you see a variable. This references a `resource_type` in the database, and annotates what type it should be at runtime.
In the `Inactive` or `Initial` phase of the Subscripton lifecycle we are least restrictive in annotating the properties; All fields/resource types
are Optional.

##### Product Block Model - Provisioning
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
In this stage whe have changed the way a Subscription domain model should look like in a certain Lifecyle state.
You also see that the `resource_type` now no-longer is Optional. It must exist in this instantiation of the class. The
model will raise a `ValidationError` upon `.save()` if typing is not filled in correctly.

##### Product Block Model - Active
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

The Class is now defined in it's most strict form, in other words in the Active lifecycle of a subscription,
this product block model must have all resource_types filled in except for `auto_negotiation` to function correctly.

!!! Tip
    The stricter you are in defining your product block models the more you are able to leverage the built in validation
    of`Pydantic`.

#### Product Model a.k.a SubscriptionModel
Product models are very similar to Prodblock Models in that they adhere to the same principles as explained above. However
the difference to Product Block models is that they create `Subscriptions` in the database. They must always have a reference
to a customer and instead of containing other `ProductBlockModel` or `resource_types` they contain either `fixed_inputs`
which basically describe fixed product attributes or other `ProductBlockModels.`

##### Product Model - Inactive
```python hl_lines="2 5 7"
class ServicePortInitial(
    SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.INITIAL, SubscriptionLifecycle.TERMINATED]
):
    domain: Domain
    port_speed: PortSpeed

    port: Optional[ServicePortBlockInactive] = None
```

In the above example you can observe the lifecyle definition as per the `ProductBlockModels`. Below that you see `fixed_inputs`
These can be of any type, however if they are a `SubClass` of a `ProductBlockModel` the code will automatically create
a database instance of that object.

##### Product Model -  Provisioning and Active
```python hl_lines="6 12"
class ServicePortProvisioning(
    ServicePortInitial, lifecycle=[SubscriptionLifecycle.PROVISIONING]
):
    domain: Domain
    port_speed: PortSpeed
    port: ServicePortBlockProvisioning


class ServicePort(ServicePortProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    domain: Domain
    port_speed: PortSpeed
    port: ServicePortBlock

```

Again you can observe how the Product definition changes depending on the lifecycle. It annotates a different type
to the `port` property in `SubscriptionLifecycle.ACTIVE` compared to `SubscriptionLifecycle.PROVISIONING`.

### Advanced Use Cases
#### Crossing the subscription boundary
As mentioned before an advanced usecase would be to use `ProductBlockModels` from other Subscriptions.

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
onwership. It basically will treat it as a `read-only` property.

#### Union types
There may also be a case where a user would like to define two different types to a `ProductBlockModel` propery.
This can be achieved by using the `Union` type decorator.

!!! danger
    When using this method be sure as to declare the **Most** specific type first. This is how Pydantic attempts to cast
    types to the property. For more background as to why, [read here](https://pydantic-docs.helpmanual.io/usage/types/#unions)

```python hl_lines="4"
class ServicePort(ServicePortProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    domain: Domain
    port_speed: PortSpeed
    port: Union[ServicePortBlock, DifferentServicePortBlock]
```
