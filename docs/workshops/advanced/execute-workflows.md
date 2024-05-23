The topology in the previous section will be used in the workshop as an example of what a network could look like.
Obviously it is possible to create any "physical" topology you like and build the "logical" topology that matches
using th Workflow Orchestrator.


### Putting initial data in place

The first thing we are going to do is populate Netbox with some initial data such as Manifacturers and Device types as well as some networks allocated for:

* Loopback addressing
* Core links addressing

This is done using the task "Netbox Bootstrap" under the tasks submenu.

Once the workflow has successfully ran, we can login into netbox (admin/admin) and check the situation: we should see some vendors and some network device models.
In the IPAM section we are going to reserve the first address of the loopback newtworks since certain network devices dont like "network addresses" to be used as loopback addresses.

* from the IPv4 prefix 10.0.127.0/24 we allocate the address 10.0.127.0 marking it with a description "RESERVED"
* from the IPv6 prefix fc00:0:0:127::/64 we allocate the address fc00:0:0:127:: marking it with a description "RESERVED"

We do this from IPAM >> Prefixes.

### Deploying the nodes

Now we should be able to deploy our routers using the `create node` workflow. This is going to be a new subscription of the product node - specifically a nokia node -  and we will have to fill an initial form.

!!! note
    Make sure that the node name is the same as the node name in containerlab (clab-orch-demo-ams-pe/clab-orch-demo-lon-pe/clab-orch-demo-par-p)

Once the workflow has successfully ran, we can login into the node just configured and take a look at the config:
```
ssh clab-orch-demo-ams-pe -l admin ##PWD: NokiaSrl1!
```
We can do the same in Netbox, and we will notice that these nodes have no interfaces, to create them in netbox, we can use a workflow. Specifically the "Update Node Interfaces" workflow that will seed the necessary data into Netbox, so we can re-use it later.

We can practice this deployin all the 3 nodes in the topology.

### Deploying core links
Once we have 2 nodes configured, we should be able to deploy a core link between them using the "create core link 10G" workflow.

You can login into the router and check the status of ISIS using:

```
show network-instance default protocols isis adjacency
show network-instance default protocols isis interface
```
