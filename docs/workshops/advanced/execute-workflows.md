The topology in the previous section will be used in the workshop as an example of what a network could look like. 
Obviously it is possible to create any "physical" topology you like and build the "logical" topology that matches 
using th Workflow Orchestrator.

### Building the topology by running workflows
The topology can be built by running the following workflows. In total we need to run 7 workflows to setup the:

* Two Node Create workflows
* Two Interface sync workflows
* One Core Link workflows
* Two Port workflow

Upon running the workflows when containerlab is enabled the Network Resource Manager, will attempt to provision the 
network and create end to end connectivity.

### Execute workflows
Please now create the topology by using the workflows provided in the orchestrator.

??? Hint
    Think about the ordering of what you need to create all components:

    * First start with nodes.
    * Seed the inventory
    * Create back bone links
    * Finally run workflows to create customer facing ports.

