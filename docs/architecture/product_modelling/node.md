# Node

The administration handoff in IMS will be different for every organisation. For
this example, it is assumed that all administration that comes with the physical
installation and first-time configuration of the network node in IMS is done
manually by a NOC engineer. This makes the node product rather simple. The only
product block that is defined holds pointers to all related information that is
stored in the operations support systems (OSS). This includes of course a
pointer to the information in IMS, and after the service has been deployed on
the network, another pointer to the related information in the NRM. To keep
track of all IP addresses and prefixes used across the network service product,
the pointers to the IPv4 and IPv6 loopback addresses on the node are also
stored.

<img height="75%" src="../node.png" title="Node Product Model" width="75%"/>

* **ims_id**: ID of the node in the inventory management system
* **nrm_id**: ID of the node in the network resource manager
* **ipv4_ipam_id**: ID of the node’s iPv4 loopback address in IPAM
* **ipv6_ipam_id**: ID of the node’s iPv6 loopback address in IPAM
