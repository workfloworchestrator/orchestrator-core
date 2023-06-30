# Port

Once a NOC engineer has physically installed a port in a node and added
some basic administration to IMS, the port is marked as available and can be
further configured through the port product. To distinguish between ports with
different speeds (1Gbit/s, 10Gbit/s, etcetera), the fixed input speed is used,
which also allows filtering available ports of the right speed. Besides pointers
to the administration of the port in IMS and the NRM, configuration options
including 802.1Q, Ethernet auto negotiation, and the use of LLDP are registered,
as well as a reference to the Node the port is installed in.

<img height="75%" src="../port.png" title="Port Product Model" width="75%"/>

* **speed**: the speed of the physical interface on the node in Mbit/s
* **ims_id**: ID of the node in the inventory management system
* **nrm_id**: ID of the node in the network resource manager
* **mode**: the port is either untagged, tagged or a link member in an aggregate
* **auto_negotiation**: enable Ethernet auto negotiation
* **lldp**: enable the link layer discovery protocol
* **node**: link to the Node product block the port is residing on
