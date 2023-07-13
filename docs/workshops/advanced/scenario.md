# Scenario

During this workshop a set of products will be created together with the needed workflows to manage enrolling network nodes into the Workflow Orchestrator and creating circuits between nodes. The products will be just complex enough to show the basic capabilities of products, product blocks, fixed inputs, resource types and workflows in the workflow orchestrator, and in addition to the lessons taught in the beginner workshop, we will cover nesting product blocks and products together.

The following attributes need to be either stored from user input, pulled from external systems, or created dynamically in external systems:

* **Node**
    * **node_id**: The ID of the node in netbox.
    * **node_name**: The name of the node
    * **ipv4_loopback**: The IPv4 loopback address on the network node.
    * **ipv6_loopback**: The IPv6 loopback address on the network node.
* **Circuit**
    * **speed**: The speed of the circuit.
    * **circuit_id**: The ID number of the circuit/cable in netbox that represents this circuit.
    * **circuit_description**: The human-friendly description for this circuit.
    * **under_maintenance**:
    * **PortPair**: A pair of exactly two Layer3Interface objects
        * **Layer3Interface**
            * **v6_ip_address**: The IPv6 address on a Layer3 network interface.
            * **Port**: A single instance of a port object
                * **port_id**: The ID number of the port in netbox
                * **port_description**: The description that will live on the port in network config.
                * **port_name**: The actual name of the port (i.e. 1/1/c1/, ge-0/0/1, etc.)
                * **node**: A reference to the Node subscription instance that this port lives on.
