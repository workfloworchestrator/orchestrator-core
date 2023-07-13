# Terminology

The data and business rules of the products and product blocks are modelled in
Workflow Orchestrator domain models. A product is a collection of one or more
product blocks, and zero or more fixed inputs. Fixed inputs are customer-facing
attributes that cannot be changed at will by a customer because they are
constrained in some way, for example by a physical constraint such as the speed
of a port or a financial constraint such as the maximum capacity of a service.
Product blocks are collections of resource types (customer-facing attributes)
that together describe a set of attributes that can be repeated one or more
times within a product and can optionally point to other product blocks. A
product block is a logical collection of resource types that taken together
make reusable instances. They can be referenced many times from within other
products and make it possible to build a logical topology of the network within
the orchestrator database. A subscription is a product instantiation for a
specific customer. See the rest of the Workflow Orchestrator documentation for
more details.
