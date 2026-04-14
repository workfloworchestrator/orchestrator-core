# L2 Point-to-Point

The Layer 2 point-to-point service is modelled using two product blocks. The
l2_point_to_point product block holds the pointers to IMS and the NRM, the speed
of the circuit, and whether the speed policer is enabled or not, as well as
pointers to the two service attach points. The latter are modelled with the
L2_service_attach_point product block and keep track of the port associated with
that endpoint and, in the case where 802.1Q has to be enabled, the VLAN range
used. The service can either be deployed protected or unprotected in the service
provider network. This is administered with the fixed input protection_type.

```mermaid
classDiagram
    namespace L2_point_to_pointProduct {
        class Fixed Inputs {
            +protection_type "Protection Type"
        }
        class L2_ptp_virtual_circuit_block {
            +ims_id: ims_id
            +nrm_id: nrm_id
            +speed: integer
            +speed_policer: boolean
            +sap: list[L2_service_attach_point_block]
        }
        class L2_service_attach_point_block {
            +vlan_range: vlan_range_type
            +port: Port_block
        }
    }
    namespace Port_Product subscription {
        class Port_block {
            +device: DeviceBlock
            +port_name: str
        }
    }

    L2_ptp_virtual_circuit_block "1" -- "2" L2_service_attach_point_block
    L2_service_attach_point_block "1" -- "n" Port_block
```

* **protection_type**: this service is either unprotected or protected
* **ims_id**: ID of the node in the inventory management system
* **nrm_id**: ID of the node in the network resource manager
* **speed**: the speed of the point-to-point service in Mbit/s
* **speed_policer**: enable the speed policer for this service
* **sap**: a constrained list of exactly two Layer2 service attach points
* **vlan_range**: range of Layer 2 labels to be used on this endpoint of the service
* **port**: link to the Port product block this service endpoint connects to
