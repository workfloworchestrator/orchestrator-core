# Product Blocks

## Defining a Product Block

!!! warning inline end
    You should only have one root Product Block on your domain model!

A Product Block is a reusable collection of product attributes that lives under a Product Type (which we covered in the [Product Types section of these docs](./product_types.md)). A Product Block allows you to define the bulk of the attributes that you want to assign to your Product definition. At it's most basic, you will have a root product block that is stored on your Product Type, as shown in the [Product Types documentation](product_types.md). Building off of that example, let's examine a basic product block by examining the `NodeBlock` product block from the [example workflow orchestrator](https://github.com/workfloworchestrator/example-orchestrator):

```python
{% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/products/product_blocks/node.py' %}
```

Breaking this product block down a bit more, we see 3 classes, `NodeBlockInactive`, `NodeBlockProvisioning`, and finally `NodeBlock`. These three classes are built off of each-other, with the lowest level class (`NodeBlockInactive`) based off of the `ProductBlockModel` base class. These classes have a number of attributes, referred to as "Resource Types", which you can [read more about here](./model_attributes.md#resource-types). Looking at this `ProductBlockModel` base class tells us a lot about how to use it in our workflows:

::: orchestrator.domain.base.ProductBlockModel
    options:
        heading_level: 3

## Nesting Product Blocks

When building a more complicated product, you will likely want to start nesting layers of product blocks. Some of these might just be used by one product, but some of these will be a reference to a product block in use by multiple product types. For an example of this, let's look at the `CorePortBlock` product block from the [example workflow orchestrator](https://github.com/workfloworchestrator/example-orchestrator):

???+ example "Example: `example-orchestrator/products/product_blocks/core_port.py`"
    ```python
    {% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/products/product_blocks/core_port.py' %}
    ```

Note in this example how the attribute `node` is type-hinted with `NodeBlockInactive`. This tells the WFO to bring in the entire tree of product blocks that are referenced, in this case, `NodeBlockInactive` when you load the `CorePortBlockInactive` into your workflow step. To read more on this concept, read through the [Product Modelling page](../../architecture/product_modelling/product_block_graph.md) in the architecture section of the docs.

## Creating Database Migrations

Just like Product types, you'll need to create a database migration to properly wire-up the product block in the orchestrator's database. A migration file for this example NodeBlock model looks like this:

??? example "Example: `example-orchestrator/migrations/versions/schema/2023-10-27_a84ca2e5e4db_add_node.py`"
    ```python linenums="1"
    {% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/migrations/versions/schema/2023-10-27_a84ca2e5e4db_add_node.py' %}
    ```

Thankfully, you don't have to write these database migrations by hand, you can simply use the `main.py db migrate-domain-models` command that is part of the [orchestrator CLI, documented here.](../cli.md#migrate-domain-models)

## Automatically Generating Product Types

If all of this seems like too much work, then good news, as all clever engineers before us have done, we've fixed that with YAML! Using the WFO CLI, you can generate your product types directly from a YAML. For more information on how to do that, check out the [CLI `generate` command documentation.](../cli.md#generate)
