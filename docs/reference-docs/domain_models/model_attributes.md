# Model Attributes

## Overview

For understanding the various attributes that can live on a domain model, let's look again at the example `Node` product and the `NodeBlock` product block from the [example workflow orchestrator](https://github.com/workfloworchestrator/example-orchestrator):

### `Node` Product Type

???+ example "Example: `example-orchestrator/products/product_types/node.py`"
    ```python linenums="1"
    {% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/products/product_types/node.py' %}
    ```

### `NodeBlock` Product Block

???+ example "Example: `example-orchestrator/products/product_blocks/node.py`"
    ```python linenums="1"
    {% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/products/product_blocks/node.py' %}
    ```

## Resource Types

A resource type is simply an attribute on a product block's python class. These are used to store values on a domain model that are *__mutable__* and will be changed over the lifecycle of the product. These are type-annotated so that they can be safely serialized and de-serialized from the database and so that pydantic can validate what you store on your domain model. When these attributes are added to a domain model, the appropriate database table must be populated via a migration. This can be handled automatically for you by [the `migrate-domain-models` command in the WFO CLI](../cli.md#migrate-domain-models). To better understand how this looks from a database standpoint, you can see the database table that needs to be populated here:

::: orchestrator.db.models.ResourceTypeTable
    options:
        heading_level: 3

You can see what a generated migration looks like that includes a new resource-type here by looking at the `"resources":` key inside of the `Node` product block :

???+ example "Example: `example-orchestrator/migrations/versions/schema/2023-10-27_a84ca2e5e4db_add_node.py`"
    ```python linenums="1"
    {% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/migrations/versions/schema/2023-10-27_a84ca2e5e4db_add_node.py' %}
    ```

Finally, when a domain model is populated, the values that you put onto the subscription are stored in the `SubscriptionInstanceValueTable` in the database, as seen here:

::: orchestrator.db.models.SubscriptionInstanceValueTable
    options:
        heading_level: 3

## Fixed Inputs

Fixed inputs are an *__immutable__* attribute that will not be changed over the lifecycle of the product. These are attributes with a hard-coded value that live on the root of the Product Type class definition. Fixed Inputs *__only__* live on Product Types, *__not__* Product Blocks. To better understand how this looks from a database standpoint, you can see the database table that needs to be populated here:

::: orchestrator.db.models.FixedInputTable
    options:
        heading_level: 3

Using the same example as above, you can see what a generated migration file looks like that includes a new resource-type here by looking at the `"fixed_inputs":` key inside of the `node Cisco` or `node Nokia` product type:

??? example
    ```python linenums="1"
    {% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/migrations/versions/schema/2023-10-27_a84ca2e5e4db_add_node.py' %}
    ```

Note that because the `Node_Type` enum has two choices (`Cisco` or `Nokia`), we generated two different products, one for each choice. Using fixed inputs in this manner allows you to easily create multiple products that share all of the same attributes aside from their fixed input without having to duplicate a bunch of domain model code. Then, when you are writing your workflows, you can handle the difference between these products by being aware of this fixed input.
