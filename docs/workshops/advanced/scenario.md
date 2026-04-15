# Scenario

During this workshop a set of products will be used together with the needed workflows to manage enrolling network
nodes into the Workflow Orchestrator and creating circuits between nodes.
The products will be just complex enough to show the basic capabilities of products, product blocks, fixed inputs,
resource types and workflows in the workflow orchestrator. We will cover nesting product blocks and products together.

## Product hiearchy example
In the diagram below you can see how all products and product blocks relate to each other. The example orchestrator
has implemented the following example products and corresponding workflows that can be used to build a basic network
topology and customer facing services:

{{ external_markdown('https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/README.md', '### Implemented products') }}

## Customers

```mermaid
flowchart
    direction LR
    cust1[Customer: NREN NOC]
    cust2[Customer: University A]
    cust3[Customer: Research Institute B]
    style cust1 rx:20,ry:20,fill:#b4c7e7,stroke-width:0px
    style cust2 rx:20,ry:20,fill:#c5e0b4,stroke-width:0px
    style cust3 rx:20,ry:20,fill:#ffe699,stroke-width:0px
```

## Example Subscription Diagram

```mermaid
%%{init: {
    'flowchart': {
        'padding': 5,
        'nodeSpacing': 5
    }
}}%%
flowchart
    direction TB
    subgraph sg_node1[Node Subscription]
        node1[NodeBlock]
    end
    subgraph sg_node2[Node Subscription]
        node2[NodeBlock]
    end
    subgraph sg_node3[Node Subscription]
        node3[NodeBlock]
    end
    subgraph sg_port1[Port Subscription]
        port1[PortBlock]
    end
    subgraph sg_port2[Port Subscription]
        port2[PortBlock]
    end
    subgraph sg_port3[Port Subscription]
        port3[PortBlock]
    end
    node1 --- port1
    node2 --- port2
    port3 --- node3
    subgraph sg_l2ptp[L2PointToPoint subscription]
        direction LR
        l2ptp_sap1[SAPBlock]
        l2ptp_vc[VirtualCircuitBlock]
        l2ptp_sap2[SapBlock]
        l2ptp_sap1 --- l2ptp_vc
        l2ptp_vc --- l2ptp_sap2
    end
    port1 --- l2ptp_sap1
    l2ptp_sap2 --- port3
    subgraph sg_l2vpn[L2VPN subscription]
        l2vpn_sap1[SAPBlock]
        l2vpn_sap2[SAPBlock]
        l2vpn_sap3[SAPBlock]
        l2vpn_vc[VirtualCircuitBlock]
        l2vpn_sap1 --- l2vpn_vc
        l2vpn_sap2 --- l2vpn_vc
        l2vpn_vc --- l2vpn_sap3
    end
    port1 --- l2vpn_sap1
    port2 --- l2vpn_sap2
    l2vpn_sap3 --- port3


    style sg_node1 rx:20,ry:20,fill:#b4c7e7
    style sg_node2 rx:20,ry:20,fill:#b4c7e7
    style sg_node3 rx:20,ry:20,fill:#b4c7e7
    style sg_port1 rx:20,ry:20,fill:#c5e0b4
    style sg_port2 rx:20,ry:20,fill:#ffe699
    style sg_port3 rx:20,ry:20,fill:#c5e0b4
    style sg_l2vpn rx:20,ry:20,fill:#ffe699
    style sg_l2ptp rx:20,ry:20,fill:#c5e0b4

    classDef default rx:10,ry:10,fill:#ff9300,stroke:#333,stroke-width:1px
```


!!! Hint
    Take some time to explore the module described in above. It shows how the product modelling is done in Python.
    Once you are familiar with the code. Continue with the workshop
