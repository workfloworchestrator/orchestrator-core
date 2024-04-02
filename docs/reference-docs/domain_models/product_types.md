# Product Types

## Defining a Product

A Product type (often referred to simply as a product) is the top level object of a domain model. A product is effectively the template used for creating a subscription instance, and you can instantiate as many of these as you want. To see an example product model, you can see a very simple Node product type from the [example workflow orchestrator](https://github.com/workfloworchestrator/example-orchestrator):

```python
{% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/products/product_types/node.py' %}
```

!!! info "Type Hints"
    Notice how type hints are used on these classes, as the orchestrator uses these types for pydantic validations and for type safety when serializing data into and out of the database.

!!! abstract inline end "Fixed Inputs"
    When a hard coded value is stored on product model, like `Node_Type` is here, it is called a Fixed Input. Read more about Fixed Inputs [here](fixed_inputs.md)

Breaking this product down a bit more, we see 3 classes, `NodeInactive`, `NodeProvisioning`, and finally `Node`. These three classes are built off of each-other, with the lowest level class (`NodeInactive`) based off of the `SubscriptionModel` base class. Each class has two simple attributes, one is the Fixed Input of `Node_Type`, and the other is the root product block `node`. Each one of these classes represents the `Node` product in its various lifecycle states, which are defined here in the `SubscriptionLifecycle` enum:

::: orchestrator.types.SubscriptionLifecycle
    options:
        heading_level: 3

To fully understand the Subscription Model, it's best to look at the `SubscriptionModel` itself in the code. Here you can also see the various methods available for use on these Subscription instances when you are using them in your workflow code:

::: orchestrator.domain.base.SubscriptionModel
    options:
        heading_level: 3

## Subscription Model Registry

When you define a Product Type as a domain model in python, you also need to register it in the subscription model registry, by using the `SUBSCRIPTION_MODEL_REGISTRY` dictionary, like is shown here in the example orchestrator:

```python
{% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/products/__init__.py' %}
```

## Creating Database Migrations

After defining all of the components of a Product type, you'll also need to create a database migration to properly wire-up the product in the orchestrator's database. A migration file for this example Node model looks like this:

??? quote "Source code in `example-orchestrator/migrations/versions/schema/2023-10-27_a84ca2e5e4db_add_node.py`"
    ```python linenums="1"
    {% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/migrations/versions/schema/2023-10-27_a84ca2e5e4db_add_node.py' %}
    ```

Thankfully, you don't have to write these database migrations by hand, you can simply use the `main.py db migrate-domain-models` command that is part of the [orchestrator CLI, documented here.](../../cli/#migrate-domain-models)

## Automatically Generating Product Blocks

If all of this seems like too much work, then good news, as all clever engineers before us have done, we've fixed that with YAML! Using the WFO CLI, you can generate your product types directly from a YAML. For more information on how to do that, check out the [CLI `generate` command documentation.](../../cli/#generate)