# Introduction

The workflow engine is the core of the orchestrator, it is responsible for the following functions:

* Safely and reliable manipulate customer Subscriptions from one state to the next and maintain auditability.

* Create an API through which Subscriptions can be manipulated programmatically.

* Execute step functions in order and allow the retry of previously failed process-steps in an idempotent way.

* Atomically execute workflow functions.

For more details on what constitutes a workflow, refer to [this section of the beginner workshop.](../beginner/workflow-introduction.md)

For the purposes of this workshop, we have provided you with already functional workflows that we will be slightly modifying. The two main workflows we will be working on are `create_node` and `create_circuit`; overviews of these workflows are below:

## Node Creation workflow

The node create workflow is the first step for configuring our mock network. This is the most basic workflow example, and simply talks to our DCIM/IPAM (Netbox) to determine which nodes are ready to be enrolled in the orchestrator and then ultimately presents the user with the config to apply on that device to complete the initial provisioning of that node. The general workflow outline is as follows:

  1. Present a list of valid routers to enroll (`initial_input_form_generator`)
  2. Populate the subscription's domain model initial values(`construct_node_model`)
  3. Store the subscription in the database (Using the built-in `store_process_subscription` step)
  4. Grab IP address information that has been defined for this device in netbox (`fetch_ip_address_information`)
  5. Display the configuration to the user that they will use to provision the device and ask them to confirm once it has been applied (`provide_config_to_user`)
  6. Update the subscription state to `PROVISIONING` (Using the built-in `set_status` step)
  7. Update the subscription lifecycle state to `ACTIVE`.

  One of our tasks as part of this workshop will be to implement a new step after we set the subscription status to `PROVISIONING` that updates the status of a node in netbox from `planning` to `active`. We'll do this by creating a function called `update_node_status_netbox`.

  Additionally, we will play with adding in validations to the node create workflow that will prevent us from somehow enrolling a node more than once.

## Circuit Creation Workflow

The circuit create workflow builds upon the subscriptions created by the `node_create` workflow and allow us to further configure our mock network by creating circuits between nodes. This is a more advanced workflow example which talks to the orchestrator's DB as well as our DCIM/IPAM to grab lists of available nodes and ports, then ultimately presents the user with the config to apply on that device so that they can complete the provisioning of that circuit. The general workflow outline is as follows:

  1. Gather user input for creating the circuit (`initial_input_form_generator`)
    1. Present the user with a list of possible routers to use for the "A-side" node
    2. Present the user with a list of possible routers to use for the "B-side" node (ensuring A-side and B-side are mutually exclusive devices)
    3. Present the user with a list of available ports on each router (pulled from netbox)
  2. Populate the subscription's domain model initial values and create the planned connection in netbox(`construct_circuit_model`)
  3. Store the subscription in the database (Using the built-in `store_process_subscription` step)
  4. Talk to our IPAM to find the next free subnet to use on the circuit between these two nodes (`reserve_ips_in_ipam`)
  5. Display the configuration to the user that they will use to provision the device and ask them to confirm once it has been applied(`provide_config_to_user`)
  6. Update the subscription state to `PROVISIONING` (Using the built-in `set_status` step)
  7. Update the status of the connection in netbox from `planned` to `connected`
  8. Update the description of the subscription in the orchestrator DB.
  9. Update the subscription lifecycle state to `ACTIVE`.

  One of our tasks as part of this workshop will be to fill out the modify workflow for the circuit so that we can transition this circuit from the default maintenance mode to a normal traffic mode mode.
