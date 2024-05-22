To create a new product configuration and wire up the python, database and workflows correctly you need to create a
lot of boilerplate configuration and code. To speed up this process and make the experience as user friendly as
possible, initial configuration of what a product looks like can be created with a yaml file.

At the end of these steps the developer will have all the necessary configuration and boilerplate completed to run
the workflow and start developing on implementing the business logic.

### Step 1 - Create the product configuration file
Open the Example Orchestrator directory and list the templates directory. It should look similar to this:

```bash
~/Documents/SURF/projects/example-orchestrator
❯ ls -l templates
total 32
-rw-r--r--  1 boers001  staff  2687 Mar  7 11:28 core_link.yaml
-rw-r--r--  1 boers001  staff  2052 Mar  7 11:28 l2vpn.yaml
-rw-r--r--  1 boers001  staff  2575 Mar  7 11:28 node.yaml
-rw-r--r--  1 boers001  staff  2444 Mar  7 11:28 port.yaml
~/Documents/SURF/projects/example-orchestrator
```

This directory houses all the configuration of the initial products that the example orchestrator provides. It is a
starting point for developing new products. In this workshop we will create a new file and generate the
L2-Point-to-Point model and workflows by configuring it with this yaml file.

### Step 2 - Configure the YAML
Create a new file in the template directory called `l2-p2p.yaml`
```bash
touch templates/l2-p2p.yaml
```
This file will contain the Initial product type configuration. Please create a yaml configuration reflecting the
product model as described on the [previous page](create-your-own.md). The goal is to configure the generator to
reuse as many of the product blocks already existing in the orchestrator as possible.

!!! tip "Inspiration"
    Take a look at the `l2vpn.yaml` model for inspiration. As you can see this file has been configured in a certain
    way to reflect the configuration of the product. For more in depth documentation take a look at the [reference
    doc](../../reference-docs/cli.md#generate).

!!! danger "What can I do when I encounter errors?"
    If you get stuck just remove all generated files, edit the yaml and try again.

??? example "Answer - l2-p2p.yaml"
    When creating the YAML you should notice that you do not have to create the **SAP** product blocks again. You just
    have reference the **SAPS** in the **Virtual Circuit** configuration. In this way you start reusing existing
    building blocks that already exist in the orchestrator. We cannot reuse the existing Virtual Circuit with the
    generator due to the different limits on the amount of SAPS that can be connected to the Virtual Circuit of the
    L2 P2P product.

    #### Yaml file
    ```yaml
    config:
      summary_forms: true
    name: l2_p2p
    type: L2P2P
    tag: L2P2P
    description: "L2 Point-to-Point"
    fixed_inputs:
      - name: protection_type
        type: enum
        enum_type: str
        values:
          - protected
          - unprotected
        description: "Level of network redundancany"
    product_blocks:
      - name: l2_p2p_virtual_circuit
        type: L2P2PVirtualCircuit
        tag: VC
        description: "virtual circuit product block"
        fields:
          - name: saps
            type: list
            description: "Virtual circuit service access points"
            list_type: SAP
            min_items: 2
            max_items: 2
            required: provisioning
          - name: speed
            description: "speed of the L2VPN im Mbit/s"
            type: int
            required: provisioning
            modifiable:
          - name: speed_policer
            description: "speed policer active?"
            type: bool
            required: provisioning
            modifiable:
          - name: ims_id
            description: "ID of the L2VPN in the inventory management system"
            type: int
            required: active
          - name: nrm_id
            type: int
            description: "ID of the L2VPN in the network resource manager"
            required: active
    ```

### Step 3 - Run the generator functions
To help generate the correct file exec into the running container and run the generator:

```bash
docker exec -it example-orchestrator-orchestrator-1 /bin/bash
```

#### Product Blocks
Run the command to generate the domain models product blocks:

```bash
python main.py generate product-blocks -cf templates/l2-p2p.yaml --no-dryrun
```
The `--no-dryrun` option will immediately write the files to the `products/product_blocks` folder and create:
`l2_p2p_sap.py` and `l2_p2p_virtual_circuit.py`. This file contains the product block configuration for the l2-p2p
product and defines the strict hierarchy of virtual circuit and saps.

#### Product
Now create the product.

```bash
python main.py generate product -cf templates/l2-p2p.yaml --no-dryrun
```

This will create the file `products/product_types/l2_p2p.py`. When looking at this file you can see it created the
domain model, fixed inputs and imported the correct product blocks to be used in this subscription.


#### Workflows
Now generate the workflows. This command will always create 4 sets of workflows `create`, `modify`, `terminate` and
`validate`. These can be implemeted as the users sees fit.

Run the command:
```bash
python main.py generate workflows -cf templates/l2-p2p.yaml --no-dryrun --force
```

As you can see this file needs to be run with the --force flag as it needs to overwrite a number of configuration
files. Furthermore it will populate the files in `workflows.l2_p2p`. Feel free to take a look and see what it
already has done.

#### Database migrations
As a final step the user must generate and run the migrations to wire up the database. This is done as follows.

```bash
python main.py generate migration -cf templates/l2-p2p.yaml
python main.py db upgrade heads
```

### Step 4 -  Profit
If this has been executed without errors, you should be able to create a new subscription for the l2-p2p product by
running the create workflow through the UI. All it does is create the domain model and fill it in with some
rudimentary values from the input form, but it's a starting point. Users can now go into the workflow source code
and start implementing steps to provision the resource that is being created by the create workflow. Take some time
in the orchestrator UI to see what has been configured.

* Metadata pages
* Action menu
* Available workflows

### Step 5 - Bonus
Implement a new step in the create workflow that manipulates the subscription in a certain way. An example could be
to change the subscription description. Or any other value you can think of that exists in the subscription

??? example - "Answer"
    ```python
    @step("Update Subscription Description")
    def update(subscription: L2p2pProvisioning) -> State:
        subscription.descrtiption = "My Awesome L2P2P"
        return state | {"subscription": subscription}
    ```
