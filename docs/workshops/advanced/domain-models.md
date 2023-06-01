# Domain models

## Introduction

First read the [Architecture; TL;DR](../../architecture/tldr.md) section of the orchestrator core documentation to get an overview of the concepts that will be covered.

To put a part of the terminology in context, products are modeled using a set of product blocks. The product attributes are modeled by resource types.  By default all resource types are mutable and can be changed over the lifetime of a subscription. Fixed inputs are used to model immutable attributes.

An example of an immutable attribute is for example the speed of a circuit, which are physical properties of the interfaces, and cannot be changed without a field engineer swapping the interface with one with a different speed. Another example is an attribute that is linked to the price of a product, for example the greater the capacity of a product, the higher the price. A customer is not allowed to increase the capacity themselves, they must pay extra first.

The products and product blocks for this workshop will be modeled as follows:

* product `Node`
    * product block `NodeBlock`
        * resource type `node_id`
        * resource type `node_named`
        * resource type `ipv4_loopback`
        * resource type `ipv6_loopback`
* product `Circuit`
    * fixed input `speed`:
    * product block `CircuitBlock`
        * resource type `circuit_id`
        * resource type `circuit_description`
        * resource type `under_maintenance`
        * restricted product block reference `members` (`PortPair`, which restricts to exactly 2 `Layer3Interface` instances)
            * product block `Layer3Interface`
                * resource type `v6_ip_address`
                * product block reference `port` (`Port`)
                    * resource type `port_id`
                    * resource type `port_description`
                    * resource type `port_name`
                    * product block reference `node` (`NodeBlock`)
                        * See `NodeBlock` from the above `Node` product.

As you can see, a product can be seen as a container for fixed inputs and at least one references to a product block. A product block is a container for resources types and (optional) references to other product blocks. Finally, you can see that product block references may be nested as deep as needed and can be used by multiple products.

For more information on product blocks, as well as some exercises for how to write these from scratch, please refer to [this section of the beginner workshop.](../beginner/domain-models.md).
