# Circuit Workflow

The `create_circuit` workflow we outlined in the workflow overview section is implemented with the following StepList:

```python
begin
>> construct_circuit_model
>> store_process_subscription(Target.CREATE)
>> reserve_ips_in_ipam
>> set_status(SubscriptionLifecycle.PROVISIONING)
>> create_circuit_in_netbox
>> update_circuit_description
>> update_circuit_in_netbox
>> provide_config_to_user
>> set_circuit_in_service
>> update_circuit_in_netbox
```

To see the actual step code, go to `workflows/circuit/circuit_create.py`. covering the implementation steps of these details is generally out of scope for this workshop, they simply exist to give us a framework to build off of. It's mainly important to understand the general flow of these steps and get a feel for how we are populating the Circuit domain model.

Once you have familiarized yourself with the circuit create code, go ahead and try running it! To run it, you need to first enroll at least two nodes, and then you can proceed with setting up a circuit. Take note at the User Input step what the ISIS routing metric is (`15000000`). This is how a network engineer might set a circuit into a maintenance mode, so our workflow sets this by default with no way to change it. This is fine for the initial provisioning for a circuit, but we need to consider the full lifecycle and how it will be turned into production eventually, which leads us to the root of this exercise. Take extra note of how we are setting that metric to `15000000` in the shared circuit file, in the function `determine_isis_metric()`:

```python
def determine_isis_metric(under_maintenance: bool) -> int:
    """
    set_isis_metric determines the ISIS metric to use depending on the
    maintenance state of the circuit.

    Args:
        under_maintenance (bool): If the circuit is under the maintenance (True)
        or not (False)

    Returns:
        int: The ISIS routing metric.
    """
    if under_maintenance:
        isis_metric = 15000000
    else:
        isis_metric = 10

    return isis_metric
```

As you can see in the above function, if the circuit is not under maintenance, we should be setting the `isis_metric` to `10`.

If you dig deeper, you can see that this function is called in the `provide_config_to_user()` function where we generate the config that a network engineer would paste into a router, specifically, we pass the subscription field `subscription.circuit.under_maintenance` (think back to the domain model!) into the `determine_isis_metric()` function, then we render the config for both sides of the circuit, like so:

```python
isis_metric = determine_isis_metric(subscription.circuit.under_maintenance)

router_a_config = render_circuit_endpoint_config(
    node=subscription.circuit.members[0].port.node.node_name,
    interface=subscription.circuit.members[0].port.port_name,
    description=subscription.circuit.members[0].port.port_description,
    address=subscription.circuit.members[0].v6_ip_address,
    isis_metric=isis_metric,
)
router_b_config = render_circuit_endpoint_config(
    node=subscription.circuit.members[1].port.node.node_name,
    interface=subscription.circuit.members[1].port.port_name,
    description=subscription.circuit.members[1].port.port_description,
    address=subscription.circuit.members[1].v6_ip_address,
    isis_metric=isis_metric,
)
```

Since we already have a modify workflow defined, go ahead and try running it to see if it changes the metric like you would expect. If everything were working, the `under_maintenance` boolean in the subscription would be set to `False` and the metric in the configuration would be set to `10`.

To run the modify workflow, navigate to a circuit subscription instance in the orchestrator GUI (create one if you haven't already), click the `Actions` tab, and then click on `Modify the circuit maintenance state`. When you run this workflow, you can see that it pulls in the current state of the `under_maintenance` flag and displays that to the user. If the user wishes, they can then change that and click submit. At this point, you, the astute developer you are, will notice that nothing actually happens, and the subscription domain model still has `under_maintenance` set to `True`. You also notice that the config to make the change was actually never displayed to the user. Let's fix that!

## Exercise 1: Updating the Domain Model via the Modify Workflow

The first step in fixing up our modify workflow is to make sure that we update the domain model with the input provided by the user. To do this, we need to fill out the step called `modify()`. Currently, it looks quite bleak:

```python
@step("Modify")
def modify(subscription: Circuit) -> State:
    logger.debug("This is the subscription", subscription=subscription, type=type(subscription))
    # DO SOMETHING
    return {}
```

We can see that the `modify_initial_input_form_generator()` step puts the form `user_input` onto the state as a dictionary, so we should just be able to access every field from the form directly from the `modify()` step by name if we add it as an argument to `modify()` (using the power of the `inject_args` helper provided by the `@step` decorator.) Once you have the value that the user provides in your function, go ahead and try to populate the subscription with that value. For an existing example of this, look at the node workflow to see how the input values are handled.

Try to go ahead and implement this on your own, however, if you get stuck, here is a working implementation:

??? example
    ```python
    @step("Modify")
    def modify(subscription: Circuit, under_maintenance: bool) -> State:
        logger.debug(
            "Changing circuit maintenance state",
            subscription=subscription,
            type=type(subscription),
            old_value=subscription.circuit.under_maintenance,
            new_value=under_maintenance,
        )
        # Set the subscription under_maintenance value to what the user input.
        subscription.circuit.under_maintenance = under_maintenance

        return {"subscription": subscription}
    ```

Once you have made your implementation, save the file, and the orchestrator backend will hot-reload. Run a new modify workflow on a circuit. Once you've run the workflow, you should now be able to go into the subscription data tab and see the new value for the under_maintenance field. If you get really fancy with it, click on the `Delta` button to see the exact changes to the subscription. If everything was done right, you should see the following change to the subscription:

```json
{
  "circuit": {
    "under_maintenance": false
  }
}
```

## Exercise 2: Updating the Configuration Based Off the Domain Model

Now that we are actually updating the orchestrator's view of things, we need to go ahead and make sure that our intent is actually applied to the network! Using our simple copy/paste method of applying network intent, this should be a fairly easy fix.

First things first, think back to how we are providing the config that we display to the user in the `provide_config_to_user()` step function. We are simply pulling data out of the subscription domain model and the populating strings with the values. Assuming that the CLI we are using is idempotent, we can simply re-apply all that config with the new values and the device config will be updated.

!!! warning

    Since this is just an example workshop, this will work for us. In production, you will want to use a much more robust configuration mediation engine, especially in a multi-vendor network, however, for the purposes of this workshop, copy/pasting config will suffice. Additionally, you might want to save values like the isis_metric to the domain model and create a single dispatch service like the netbox example used in this workshop.

With this in mind, all we really need to do is take the `provide_config_to_user()` step from shared, import it into our modify workflow/add it to the steplist and be off to the races!

Go ahead and try to do this on your own, however, if you get stuck, here is a working implementation:

??? example

    First, go ahead and import the step from the shared file, like so:
    ```python
    from workflows.circuit.shared import provide_config_to_user
    ```

    Now go ahead and add that to the steplist so that your steplist looks like this:

    ```python
    def modify_circuit() -> StepList:
        return (
            begin
            >> set_status(SubscriptionLifecycle.PROVISIONING)
            >> modify
            >> provide_config_to_user
            >> set_status(SubscriptionLifecycle.ACTIVE)
        )
    ```

Once you have made your implementation, save the file, and the orchestrator backend will hot-reload. Run a new modify workflow on a circuit. Once you've run the workflow and have changed the boolean flag for the maintenance state, you will be presented with a fresh set of config to be applied to the network device.

Congratulations on fixing this modify workflow!
