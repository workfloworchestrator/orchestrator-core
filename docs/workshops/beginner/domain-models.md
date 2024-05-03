# Domain models

## Introduction

First read the [Architecture; TL;DR](/orchestrator-core/architecture/tldr/)
section of the orchestrator core documentation to get an overview of the
concepts that will be covered.

To put a part of the terminology in context, products are modeled using a set
of product blocks. The product attributes are modeled by resource types.  By
default all resource types are mutable and can be changed over the lifetime of
a subscription. Fixed inputs are used to model immutable attributes.

An example of an immutable attribute is for example the speed of a network
interface, which is a physical property of the interface, and cannot be changed
without a field engineer swapping the interface with one with a different
speed. Another example is an attribute that is linked to the price of a
product, for example the greater the capacity of a product, the higher the
price. A customer is not allowed to increase the capacity himself, he has
to pay extra first.

The products and product blocks for this workshop will be modeled as follows:

* product **UserGroup**
    * product block reference **user_group** (UserGroupBlock)
* product **User**
    * fixed input **affiliation**
    * product block reference **user** (UserBlock)
* product block **UserGroupBlock**
    * resource type **group_name**
    * resource type **group_id**
* product block **UserBlock**
    * resource type **username**
    * resource type **age**
    * resource type **user_id**
    * product block reference **group** (UserGroupBlock)

A product can be seen as a container for fixed inputs and (at least one)
references to a product block, and a product block as a container for resources
types and (optional) references to other product blocks. Product block
references may be nested as deep as needed.

## Exercise 1: create UserGroup product block

Read the [Domain models](../../architecture/application/domainmodels.md)
section of the orchestrator core documentation to learn more about domain
models and how they are defined. For now, skip the code examples *Product Model
a.k.a SubscriptionModel* and *Advanced Use Cases*.

Use the following skeleton to create the file `user_group.py` in the
`products/product_blocks` folder and define the `UserGroupBlockInactive`,
`UserGroupBlockProvisioning` and `UserGroupBlock` domain models describing the
user group product block in the lifecycle states `INITIAL`, `PROVISIONING` and
`ACTIVE`:

```python
from typing import Optional

from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle

# UserGroupBlockInactive with all resource types optional
...

# UserGroupBlockProvisioning with only resource type group_id optional
...

# UserGroupBlock with all resource types mandatory
...
```

!!! example

    for inspiration look at an example implementation of the [user group product block
    ](https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/products/product_blocks/user_group.py)

## Exercise 2: create UserGroup product

Return to the [Domain models](../../architecture/application/domainmodels.md)
section of the orchestrator core documentation and look at the code example
*Product Model a.k.a SubscriptionModel*.

Use the following skeleton to create the file `user_group.py` in the
`products/product_types` folder and define the `UserGroupInactive`,
`UserGroupProvisioning` and `UserGroup` domain models describing the user group
product in its different lifecycle states:

```python
from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle

from products.product_blocks.user_group import (
    UserGroupBlock,
    UserGroupBlockInactive,
    UserGroupBlockProvisioning,
)

# UserGroupInactive
...

# UserGroupProvisioning
...

# UserGroup
...
```

!!! example

    for inspiration look at an example implementation of the [user group product
    ](https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/products/product_types/user_group.py)

## Exercise 3: create User product block

Use the following skeleton to create the file `user.py` in the
`products/product_blocks` folder and define the `UserBlockInactive`,
`UserBlockProvisioning` and `UserBlock` domain models describing the user group
product block in its different lifecycle states:

```python
from typing import Optional

from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle

from products.product_blocks.user_group import (
    UserGroupBlock,
    UserGroupBlockInactive,
    UserGroupBlockProvisioning,
)

# UserBlockInactive with only product block reference group mandatory
...

# UserBlockProvisioning with only resource type user_id and age optional
...

# UserBlock with only resource type age optional
...
```

!!! example

    for inspiration look at an example implementation of the [user product block
    ](https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/products/product_blocks/user.py)

## Exercise 4: create User product

Use the following skeleton to create the file `user.py` in the
`products/product_types` folder and define the `UserInactive`,
`UserProvisioning` and `User` domain models describing the user product in its
different lifecycle states.

Note that the `strEnum` type from the orchestrator is used, which uses the
standard python module `enum` to define an enumeration of strings, to create a
type to be used for the fixed input `affiliation`.

```python
from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle, strEnum

from products.product_blocks.user import (
    UserBlock,
    UserBlockInactive,
    UserBlockProvisioning,
)


class Affiliation(strEnum):
    internal = "internal"
    external = "external"


# UserInactive(SubscriptionModel
...

# UserProvisioning
...

# User
...
```

!!! example

    for inspiration look at an example implementation of the [user product
    ](https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/products/product_types/user.py)
