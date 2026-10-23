---
# tutorial | how-to | reference | explanation | mixed
diataxis: mixed
reviewed: true
---

# Product Types
<!-- diataxis: mixed -->

## Defining a Product Type
<!-- diataxis: mixed -->
<!-- TODO: mostly explanation, move generated docs to reference docs, then link to them -->

A Product Type (often referred to simply as a product) is the top level object of a domain model. A product is effectively the template used for creating a subscription, and you can instantiate as many instances of these as you want. To see an example product model, you can see a very simple Node product type from the [example workflow orchestrator](https://github.com/workfloworchestrator/example-orchestrator):

```python
{% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/products/product_types/node.py' %}
```

!!! info "Type Hints"
    Notice how type hints are used on these classes—The WFO uses these types for pydantic validations and for type safety when serializing data into and out of the database. If you're not familiar with type hinting, learn about the benefits from [PEP 484](https://peps.python.org/pep-0484/)!

!!! abstract inline end "Fixed Inputs"
    When a hard coded value is stored on product model, like `Node_Type` is here, it is called a Fixed Input. Read more about Fixed Inputs [here](model-attributes.md#fixed-inputs)

Breaking this product down a bit more, we see 3 classes, `NodeInactive`, `NodeProvisioning`, and finally `Node`. These three classes are built off of each-other, with the lowest level class (`NodeInactive`) based off of the `SubscriptionModel` base class. Each class has two simple attributes, one is the Fixed Input of `Node_Type`, and the other is the root product block `node`. Each one of these classes represents the `Node` product in its various lifecycle states, which are defined here in the `SubscriptionLifecycle` enum:

::: orchestrator.core.types.SubscriptionLifecycle
    options:
        heading_level: 3

<!-- TODO: the term "Subscription Model" appears without prior definition. It seems to be used interchangeably with "Domain Model". -->

To fully understand the Subscription Model, it's best to look at the `SubscriptionModel` itself in the code. Here you can also see the various methods available for use on these Subscription instances when you are using them in your workflow code:

::: orchestrator.core.domain.base.SubscriptionModel
    options:
        heading_level: 3

<!-- TODO: not sure if this implementation detail should be explained here. It is probably better off as reference documentation. -->
It is also quite helpful to see how the Product Type is stored in the database—To see this, look at the `ProductTable` model as it shows all of the attributes stored in the database to store your WFO products:

::: orchestrator.core.db.models.ProductTable
    options:
        heading_level: 3

## Registering a product type
<!-- diataxis: explanation -->
<!-- TODO: link to How-To that guides the user through registering a product type -->

A product type must be registered both in code and in the database.
This ensures that a subscription (an "instance" of a product type) can be serialized from Python to
the database, and deserialized when reading from the database into Python.

During orchestrator-core startup, product types registered in code are mapped to the corresponding database
registrations based on their unique name.
The product id is kept in memory for future database queries.
When a product type is missing its database registration, an error is logged and the application refuses to start.

This loose coupling makes the same code definitions usable against databases with different id's.

### Code registration
<!-- diataxis: explanation -->

The product type's python definition needs to be registered in the subscription model registry by using the
`SUBSCRIPTION_MODEL_REGISTRY` dictionary, like is shown here in the [example workflow orchestrator](https://github.com/workfloworchestrator/example-orchestrator):

```python
{% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/products/__init__.py' %}
```

This registry forms the central source of truth for generating API schemas, search definitions and more.  

### Database registration
<!-- diataxis: explanation -->

A product type and all of its components like fixed inputs and product blocks, must be registered in the database.
This is done through a database migration. An example migration from the example-orchestrator for the Node product:

??? example "Example: `example-orchestrator/migrations/versions/schema/2023-10-27_a84ca2e5e4db_add_node.py`"
    ```python linenums="1"
    {% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/migrations/versions/schema/2023-10-27_a84ca2e5e4db_add_node.py' %}
    ```

<!-- TODO remove this line after we have a How-To guide for end-to-end product creation, then make the parent section refer to that guide -->
Thankfully, you don't have to write these database migrations by hand, you can simply use the `main.py db migrate-domain-models` command that is part of the [orchestrator CLI, documented here.](../cli.md#migrate-domain-models)

## Automatically Generating Product Types
<!-- diataxis: explanation -->
<!-- TODO expand this section (or on a new page) with details about why the product generator was added, the structure (possibly already documented elsewhere). This section can then be used to link from a tutorial/how-to on using the product generator. -->

If all of this seems like too much work, then good news, as all clever engineers before us have done, we've fixed that with YAML! Using the WFO CLI, you can generate your product types directly from a YAML. For more information on how to do that, check out the [CLI `generate` command documentation.](../cli.md#generate)
