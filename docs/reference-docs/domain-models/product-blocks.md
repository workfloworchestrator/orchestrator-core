---
# tutorial | how-to | reference | explanation | mixed
diataxis: mixed
reviewed: true
---

# Product Blocks
<!-- diataxis: mixed -->

## Defining a Product Block
<!-- diataxis: mixed -->
<!-- TODO: mostly explanation, move generated docs of ProductBlockModel to reference, then link to it --> 

!!! warning inline end
    You should only have one root Product Block on your domain model!

A Product Block is a reusable collection of product attributes that lives under a Product Type (which we covered in the [Product Types section of these docs](./product-types.md)). A Product Block allows you to define the bulk of the attributes that you want to assign to your Product definition. At it's most basic, you will have a root product block that is stored on your Product Type, as shown in the [Product Types documentation](product-types.md). Building off of that example, let's examine a basic product block by examining the `NodeBlock` product block from the [example workflow orchestrator](https://github.com/workfloworchestrator/example-orchestrator):

```python
{% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/products/product_blocks/node.py' %}
```

Breaking this product block down a bit more, we see 3 classes, `NodeBlockInactive`, `NodeBlockProvisioning`, and finally `NodeBlock`. These three classes are built off of each-other, with the lowest level class (`NodeBlockInactive`) based off of the `ProductBlockModel` base class. These classes have a number of attributes, referred to as "Resource Types", which you can [read more about here](./model-attributes.md#resource-types). Looking at this `ProductBlockModel` base class tells us a lot about how to use it in our workflows:

::: orchestrator.core.domain.base.ProductBlockModel
    options:
        heading_level: 3

## Nesting Product Blocks
<!-- diataxis: explanation -->

When building a more complicated product, you will likely want to start nesting layers of product blocks. Some of these might just be used by one product, but some of these will be a reference to a product block in use by multiple product types. For an example of this, let's look at the `CorePortBlock` product block from the [example workflow orchestrator](https://github.com/workfloworchestrator/example-orchestrator):

???+ example "Example: `example-orchestrator/products/product_blocks/core_port.py`"
    ```python
    {% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/products/product_blocks/core_port.py' %}
    ```

Note in this example how the attribute `node` is type-hinted with `NodeBlockInactive`. This tells the WFO to bring in the entire tree of product blocks that are referenced, in this case, `NodeBlockInactive` when you load the `CorePortBlockInactive` into your workflow step. To read more on this concept, read through the [Product Modeling page](../../architecture/product-modeling/product-block-graph.md) in the architecture section of the docs.

## Creating Database Migrations
<!-- diataxis: explanation -->

Just like Product types, you'll need to create a database migration to properly wire-up the product block in the orchestrator's database. A migration file for this example NodeBlock model looks like this:

??? example "Example: `example-orchestrator/migrations/versions/schema/2023-10-27_a84ca2e5e4db_add_node.py`"
    ```python linenums="1"
    {% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/migrations/versions/schema/2023-10-27_a84ca2e5e4db_add_node.py' %}
    ```

Thankfully, you don't have to write these database migrations by hand, you can simply use the `main.py db migrate-domain-models` command that is part of the [orchestrator CLI, documented here.](../cli.md#migrate-domain-models)

## Automatically Generating Product Types
<!-- diataxis: explanation -->
<!-- TODO this section can be fleshed out more with details about why the product generator was added, the structure, which may now be documented elsewhere in the codebase. This section can then be used to link from a tutorial/how-to on using the product generator. 

If all of this seems like too much work, then good news, as all clever engineers before us have done, we've fixed that with YAML! Using the WFO CLI, you can generate your product types directly from a YAML. For more information on how to do that, check out the [CLI `generate` command documentation.](../cli.md#generate)
