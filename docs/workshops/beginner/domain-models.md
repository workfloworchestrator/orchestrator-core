# Domain models

## Introduction

First read the [Architecture; TLDR](/orchestrator-core/architecture/tldr/)
section of the orchestrator core documentation to get a first overview of the
concepts that will be covered.

To put a part of the terminology in context, products are modeled using a set
op product blocks. The product attributes are modelled by resource types.  By
default all resource types are mutable and can be changed over the lifetime of
a subscription. Fixed inputs are used to model immutable attributes.

An example of an immutable attribute is for example the speed of a network
interface, which is a physical property of the interface, and cannot be changed
without a field engineer swapping the interface with one with a different
speed. Another example is an attribute that is linked to the price of a
product, one is not allowed to just upgrade such a product without paying
extra.

The products and product blocks for this workshop will be modelled as follows:

* product **UserGroup**
    * product block reference **settings** (UserGroupBlock)
* product **User**
    * fixed input **affiliation**
    * product block reference **settings** (UserBlock)
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

Now read the [Domain
models](/orchestrator-core/architecture/application/domainmodels/) section of
the orchestrator core documentation to learn more about domain models and how
they are defined.

## Exercise 1: create UserGroup product block

Use the following skeleton to create the file `user_group.py` in the
`product_blocks` folder of the `example-orchestrator` and define the
`UserGroupBlockInactive`, `UserGroupBlockProvisioning` and `UserGroupBlock`
user group product blocks in their different lifecycle states:

```
from orchestrator.domain.base import ProductBlockModel
from orchestrator.types import SubscriptionLifecycle

...
```

**Spoiler**: for inspiration look at an example implementation of the [user
group product
block](https://github.com/hanstrompert/example-orchestrator/blob/master/products/product_blocks/user_group.py)

