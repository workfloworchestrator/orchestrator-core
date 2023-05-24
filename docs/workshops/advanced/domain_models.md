# Domain models

## Introduction

First read the [Architecture; TLDR](/orchestrator-core/architecture/tldr/) section of the orchestrator core documentation to get an overview of the concepts that will be covered.

To put a part of the terminology in context, products are modeled using a set of product blocks. The product attributes are modeled by resource types.  By default all resource types are mutable and can be changed over the lifetime of a subscription. Fixed inputs are used to model immutable attributes.

An example of an immutable attribute is for example the speed of a network interface, which is a physical property of the interface, and cannot be changed without a field engineer swapping the interface with one with a different speed. Another example is an attribute that is linked to the price of a product, for example the greater the capacity of a product, the higher the price. A customer is not allowed to increase the capacity themselves, they must pay extra first.

The products and product blocks for this workshop will be modeled as follows:

* product **Node**
  * **node_id**: The ID of the node in netbox.
  * **node_name**: The name of the node
  * **ipv4_loopback**: The IPv4 loopback address on the network node.
  * **ipv6_loopback**: The IPv6 loopback address on the network node.
* product **Circuit**
  * **circuit_id**: The ID number of the circuit/cable in netbox that represents this circuit.
  * **under_maintenance**:
  * **PortPair**: A pair of exactly two Layer3Interface objects
    * **Layer3Interface**
      * **v6_ip_address**: The IPv6 address on a Layer3 network interface.
      * **Port**: A single instance of a port object
        * **port_id**: The ID number of the port in netbox
        * **port_description**: The description that will live on the port in network config.
        * **port_name**: The actual name of the port (i.e. 1/1/c1/, ge-0/0/1, etc.)
        * **node**: A reference to the Node subscription instance that this port lives on.

* product **Node**
  * product block reference **node** (NodeBlock)
* product **Circuit**
  * fixed input **speed**
  * product block reference **circuit** (CircuitBlock)
* product block **NodeBlock**
  * resource type **group_name**
  * resource type **group_id**
* product block **Port**
  * resource type **port_id**
  * resource type **port_description**
  * resource type **port_name**
  * product block reference **Node** (NodeBlock)
* product block **Layer3Interface**
  * product block reference **port** (Port)
  * resource type **v6_ip_address**
* restricted product block **PortPair** (List of exactly two Port objects)
* product block **CircuitBlock**
  * restricted product block reference **members** (PortPair)
  * resource type **circuit_id**
  * resource type **under_maintenance**

A product can be seen as a container for fixed inputs and (at least one) references to a product block, and a product block as a container for resources types and (optional) references to other product blocks. Product block references may be nested as deep as needed.

<!-- ## Exercise 1: create Node product block

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

from products.product_blocks.user_group import UserGroupBlock, UserGroupBlockInactive, UserGroupBlockProvisioning

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

from products.product_blocks.user_group import UserGroupBlock, UserGroupBlockInactive, UserGroupBlockProvisioning

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

from products.product_blocks.user import UserBlock, UserBlockInactive, UserBlockProvisioning

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
    ](https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/products/product_types/user.py) -->
