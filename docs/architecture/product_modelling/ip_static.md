# IP static

The modelling of the IP static service is slightly more difficult. Luckily, we
are again able to reuse existing product blocks and add or change attributes to
meet our needs. First of all, a fixed input is used to distinguish between
different types of IP services, in our case it is used to distinguish between
static and BGP routing. The Ip_static_virtual_circuit product block reuses the
L2_ptp_virtual_circuit product block and adds the ability to administer
additional IP settings such as the use of multicast and whether a CERT filter
is enabled or not. The list of service attach points is overridden, this time
to reflect the fact that the IP static service only has one endpoint. The layer
3 service attach point extends the one at layer 2 and adds a list of customer
prefixes, the IPv4/IPv6 MTU, and the IPv4/IPv6 point-to-point addresses used.
For this example, we chose to bundle the IP settings in a separate product
block to make it possible to be reused by other products, but we could also
just have extended the Ip_static_virtual_circuit product block.

<img height="75%" src="../ip_static.png" title="IP Static Product Model" width="75%"/>

* **ip_routing_type**: either Static or BGP, for this product set to Static
* **customer_prefixes**: list of IPAM ID’s of the customer IP prefixes
* **customer_ipv4_mtu**: the customer IPv4 maximum transmission unit
* **customer_ipv6_mtu**: the customer IPv6 maximum transmission unit
* **ptp_ipv4_ipam_id**: the IPAM id of the IPv4 point-to-point prefix
* **ptp_ipv6_ipam_id**: the IPAM id of the IPv6 point-to-point prefix
* **multicast**: enable multicast
* **cert_filter**: enable CERT filter
