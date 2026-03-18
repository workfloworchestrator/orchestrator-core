# L2 Point-to-Point

The Layer 2 point-to-point service is modelled using two product blocks. The
l2_point_to_point product block holds the pointers to IMS and the NRM, the speed
of the circuit, and whether the speed policer is enabled or not, as well as
pointers to the two service attach points. The latter are modelled with the
L2_service_attach_point product block and keep track of the port associated with
that endpoint and, in the case where 802.1Q has to be enabled, the VLAN range
used. The service can either be deployed protected or unprotected in the service
provider network. This is administered with the fixed input protection_type.

<img height="75%" src="../l2_point_to_point.png" title="L2 Point-to-Point Product Model" width="75%"/>

* **protection_type**: this service is either unprotected or protected
* **ims_id**: ID of the node in the inventory management system
* **nrm_id**: ID of the node in the network resource manager
* **speed**: the speed of the point-to-point service in Mbit/s
* **speed_policer**: enable the speed policer for this service
* **sap**: a constrained list of exactly two Layer2 service attach points
* **vlan_range**: range of Layer 2 labels to be used on this endpoint of the service
* **port**: link to the Port product block this service endpoint connects to
