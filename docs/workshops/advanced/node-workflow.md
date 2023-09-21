# Node Workflow

## Exercise 1: Update Netbox Status

The `create_node` workflow we outlined in the workflow overview section is implemented with the following StepList:

```python
begin
>> construct_node_model
>> store_process_subscription(Target.CREATE)
>> fetch_ip_address_information
>> set_status(SubscriptionLifecycle.PROVISIONING)
>> provide_config_to_user
>> set_node_to_active
>> update_node_in_netbox
```

To see the actual step code, go to `workflows/node/node_create.py`. Covering the implementation steps of these details is generally out of scope for this workshop, they simply exist to give us a framework to build off of. The important concept to understand is that we are going to fill out the currently empty `set_node_to_active` step to actually perform the functions we need done in netbox. Most of the heavy lifting with netbox is performed in the netbox single dispatch service we've included with the workshop code at `services/netbox.py` and `products/services/netbox/netbox.py`. To keep things simple, we won't cover _how_ this single dispatch service works, but rather, just use it. Generally, to use this service, you pass the subscription instance that you want to update in netbox to the `build_payload()` function and netbox will be updated for you, as shown in the last step of the node create workflow:

```python
@step("Update Node in Netbox")
def update_node_in_netbox(subscription: NodeProvisioning) -> State:
    """Updates a node in Netbox"""
    netbox_payload = build_payload(subscription.node, subscription)
    return {"netbox_payload": netbox_payload.dict(), "netbox_updated": netbox.update(netbox_payload)}

```

### Why Update Node Status Externally?

The goal of the orchestrator is generally not to store data in the orchestrator's DB, but rather, to store pointers to data in external systems and keep track of those data. With the way that `create_node` is currently implemented, we have a bug where it is possible to enroll the same node multiple times, due to how we are filtering our list of nodes. To see this bug, take a look at the first few lines of the `initial_input_form_generator` function in `create_node.py`, copied here for your convenience:

```python
def initial_input_form_generator(product_name: str) -> FormGenerator:
    """Generates the Node Form to display to the user."""
    logger.debug("Generating initial input form")
    devices = netbox.get_devices(status="planned")
    choices = [device.name for device in devices]
    DeviceEnum = Choice("Planned devices", zip(choices, choices))
```

The important part of this function here is `devices = netbox.get_devices(status="planned")`, where we fetch all devices in netbox that are in the `planned` state using the netbox service and then we construct the rest of the initial input form to present a list of available nodes to run this workflow against. Since we don't have anything in the workflow that then ever changes that status in netbox from planned to a different state, there is nothing stopping us from enrolling the same router over and over again, which is of course not desirable.

### Implement The Update Step

The example netbox service provided with this workshop code is very convenient for updating data in netbox via the orchestrator. The general way this works, is that we have pre-written dataclasses that match the expected netbox API payloads, and made an orchestrator service that you can pass the subscription object to. Once the netbox service receives the subscription object, all you need to do is update the domain model with the right value, and then the code in the `update_node_in_netbox` step of the node create workflow will call the netbox service and update things appropriately in that system. As mentioned above, using this single dispatch netbox client, we simply use the `netbox.build_payload()` method, and pass in a domain model to update netbox. This works very cleanly, as single dispatch looks at the type hint of the domain model to determine how to send the payload. Note in the examples given in the code that we send both the specific product block that we want updated in the external system as well as the overall subscription so that the netbox service can use metadata from the subscription, such as general subscription attributes or information from other product blocks that are part of this subscription when constructing the payload.

To take advantage of this netbox service to implement the update step, all you need to do is the following in the `set_node_to_active` step of the node workflow:

1. Modify the subscription object so that you set the `node_status` domain model field to active
2. Return the subscription object so that the subscription is saved in the database, thus completing updating the domain model.

For a hint, look at lines 60-63 of `workflows/node/node_create.py` to see how to update the domain model for this subscription—Try to do this on your own, however, if you get stuck, here is a working implementation:

??? example
    ```python
    @step("Set Node to active")
    def set_node_to_active(subscription: NodeProvisioning) -> State:
        """Updates a node to be Active"""
        subscription.node.node_status = "active"
        return {"subscription": subscription}
    ```

Once you have made your implementation, save the file, and the orchestrator backend will hot-reload. Run a new node create workflow on a node. Once you've run the workflow, you should now be able to go into netbox and see nodes set to active, like so:

![Netbox Active Devices](../images/netbox_devices_active.png "Netbox Active Devices")

!!! warning

    Keep in mind that This won't go back and fix the nodes that have been enrolled before we implemented this fix. In a production deployment you would need to go and fix this data manually or via some scripting, however, in this scenario, we can simply reset our environment to a blank slate like so:

    ```bash
    jlpicard@ncc-1701-d:~$ docker compose down -v && docker compose up -d
    ```
