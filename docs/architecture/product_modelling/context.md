# Context

The models described further on assume an Ethernet network that consists of
nodes where each node has physical ports. Network services have endpoints that
connect to ports. The attributes that are specific to an endpoint are modelled
as a service attach point. Examples of such attributes are the layer two
label(s) used on that port or a point-to-point IP address. An inventory
management system (IMS) is used to keep track of everything that is being
deployed, and a network resource manager (NRM), such as NSO or Ansible, is used
to provision the services on the network. All IP addresses and prefixes are
stored in an IP address management (IPAM) tool.
