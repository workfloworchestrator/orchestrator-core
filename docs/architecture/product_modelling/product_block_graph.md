# Product Block Instance Graph

A subscription for a specific customer for a product that is deployed on the
network is stored in the Workflow Orchestrator database. The notion of
subscription ownership allows for fine-grained control over which customer is
allowed to change what attribute. By correctly adding references from one
product block to another, a graph of product block instances is generated that
accurately reflects the relations between the snippets of network node
configuration that are deployed to the network. The graph is automatically added
to when a new subscription is created, allowing easy and intuitive navigation
through all configuration data. Once every network service is modelled and
provisioned to the network through the Workflow Orchestrator, every line of
network node configuration can be linked to the corresponding subscription that
holds the configuration parameters.

The example below shows the product block instance graph for a L2 point-to-point
and a L2 VPN service between three ports on three different nodes. The nodes are
owned by the respective NREN’s Network Operations Centre (NOC). University A has
ports on nodes on two different locations, and uses a L2 point-to-point service
to connect these locations. Research Institute B has one port of its own, and
uses a L2 VPN service for their collaboration with the university. The business
rules that describe the (optional) authorisation logic for connecting
subscriptions from different customers to each other are coded in the Workflow
Orchestrator workflows related to these products.

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
