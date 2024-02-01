# What is a workflow and how does it work?
The workflow engine is the core of the software, it has been created to execute a number of functions.

- Safely and reliable manipulate customer `Subscriptions` from one state to the next and maintain auditability.
- Create an API through which programmatically `Subscriptions` can be manipulated.
- Execute step functions in order and allow the retry of previously failed process-steps in an idempotent way.
- Atomically execute workflow functions.

## Create

The "base" workflow out of a set is the `CREATE` workflow. That will create a subscription and all of the associated workflows "nest" under that.

### Create migration

The migration needs to define a specific set of parameters:

```python
params_create = dict(
    name="create_node_enrollment",
    target="CREATE",
    description="Create Node Enrollment Service",
    tag="NodeEnrollment",
    search_phrase="Node Enrollment%",
)
```

The `name` is the actual name of the workflow as defined in the workflow code itself:

```python
@create_workflow(
    "Create Node Enrollment",
    initial_input_form=initial_input_form_generator,
    status=SubscriptionLifecycle.PROVISIONING
)
def create_node_enrollment() -> StepList:
    return (
        begin
        >> construct_node_enrollment_model
        >> store_process_subscription(Target.CREATE)
        ...
        ...
        ...
```

The `target` is `CREATE`, `description` is a human readable label and the `tag` is a specific string that will be used in all of the associated workflows.

### Create flow

Generally the initial step will be the form generator function to display information and gather user input. The first actual step (`construct_node_enrollment_model` here) is generally one that takes data gathered in the form input step (and any data gathered from external systems, etc) and constructs the populated domain model.

Note that at this point the subscription is created with a lifecycle state of `INITIAL`.

The domain model is then returned as part of the `subscription` object along with any other data downstream steps might want:

```python
@step("Construct Node Enrollment model")
def construct_node_enrollment_model(
    product: UUIDstr, customer_id: UUIDstr, esdb_node_id: int, select_node: str, url: str, uuid: str, role_id: str
) -> State:
    subscription = NodeEnrollmentInactive.from_product_id(
        product_id=product, customer_id=customer_id, status=SubscriptionLifecycle.INITIAL
    )

    subscription.ne.esdb_node_id = esdb_node_id
    subscription.description = f"Node {select_node} Initial Subscription"
    subscription.ne.esdb_node_uuid = uuid
    subscription.ne.nso_service_id = uuid4()
    subscription.ne.routing_domain = "esnet-293"

    role = map_role(role_id, select_node)
    site_id = select_node.split("-")[0] # location short name

    return {
        "subscription": subscription,
        "subscription_id": subscription.subscription_id,
        "subscription_description": subscription.description,
        "role": role,
        "site_id": site_id
    }
```

After that the the subscription is created and registered with the orchestrator:

```python
    >> store_process_subscription(Target.CREATE)
```

The subsequent steps are the actual logic being executed by the workflow. It's a best practice to have each step execute one discrete operation so in case a step fails it can be restarted. To wit if a step contained:

```python
@step("Do things rather than thing")
def do_things(subscription: NodeEnrollmentProvisioning):

    do_x()

    do_y()

    do_z()

    return {"subscription": subscription}
```

And `do_z()` fails, restarting the workflow will execute the first two steps again and that might cause problems.

The final step will make any final changes to the subscription information and change the state of the subscription to (usually) `PROVISIONING` or `ACTIVE`:

```python
@step("Update subscription name with node info")
def update_subscription_name_and_description(subscription: NodeEnrollmentProvisioning, select_node: str) -> State:
    subscription = change_lifecycle(subscription, SubscriptionLifecycle.PROVISIONING)
    subscription.description = f"Node {select_node} Provisioned (without system service)"

    return {"subscription": subscription}
```

No other magic really, when this step completes successfully the workflow is done and the active subscription will show up in the orchestrator UI.

## Associated workflows

Now with an active subscription, the associated workflows (modify, validate, terminate, etc) "nest" under the active subscription in the UI. When they are executed they are run "on" the subscription they are associated with.

Like the `CREATE` workflow they *can* have an initial form generator step but they don't necessarily need one. For example a validate workflow probably would not need any additional input since it's just running checks on an existing subscription.

These workflows have more in common with each other than not, it's mostly a matter of how they are registered with the system.

### Execution parameters

There are a few parameters to finetune workflow execution constraints. The recommended place to alter them is from the workflows module, i.e. in `workflows/__init__.py`. Refer to the examples below.

1. `WF_USABLE_MAP`: configure subscription lifecycles on which a workflow is usable

By default, the associated workflow can only be run on a subscription with a lifecycle state set to `ACTIVE`. This behavior can be changed in the `WF_USABLE_MAP` data structure:

```python
from orchestrator.services.subscriptions import WF_USABLE_MAP

WF_USABLE_MAP.update(
    {
        "validate_node_enrollment": ["active", "provisioning"],
        "provision_node_enrollment": ["active", "provisioning"],
        "modify_node_enrollment": ["provisioning"],
    }
)
```

Now validate and provision can be run on subscriptions in either `ACTIVE` or `PROVISIONING` states and modify can *only* be run on subscriptions in the `PROVISIONING` state. The exception is terminate, those workflows can be run on subscriptions in any state unless constrained here.

2. `WF_BLOCKED_BY_IN_USE_BY_SUBSCRIPTIONS`: block modify workflows on subscriptions with unterminated `in_use_by` subscriptions

By default, only terminate workflows are prohibited from running on subscriptions with unterminated `in_use_by` subscriptions. This behavior can be changed in the `WF_BLOCKED_BY_IN_USE_BY_SUBSCRIPTIONS` data structure:

```python
from orchestrator.services.subscriptions import WF_BLOCKED_BY_IN_USE_BY_SUBSCRIPTIONS

WF_BLOCKED_BY_IN_USE_BY_SUBSCRIPTIONS.update(
    {
        "modify_node_enrollment": True
    }
)
```

With this configuration, both terminate and modify will not run on subscriptions with unterminated `in_use_by` subscriptions.

3. `WF_USABLE_WHILE_OUT_OF_SYNC`: allow specific workflows on out of sync subscriptions

By default, only system workflows (tasks) are allowed to run on subscriptions that are not in sync. This behavior can be changed with the `WF_USABLE_WHILE_OUT_OF_SYNC` data structure:

```python
from orchestrator.services.subscriptions import WF_USABLE_WHILE_OUT_OF_SYNC

WF_USABLE_WHILE_OUT_OF_SYNC.extend(
    [
        "modify_description"
    ]
)
```

Now this particular modify workflow can be run on subscriptions that are not in sync.

!!! danger
    It is potentially dangerous to run workflows on subscriptions that are not in sync. Only use this for small and
    specific usecases, such as editing a description that is only used within orchestrator.

#### Initial state

The first step of any of these associated workflows will be to fetch the subscription from the orchestrator:

```python
@step("Load initial state")
def load_initial_state(subscription_id: UUIDstr) -> State:
    subscription = NodeEnrollment.from_subscription(subscription_id)

    return {
        "subscription": subscription,
    }
```

The `subscription_id` is automatically passed in.

### Validate

Validate workflows run integrity checks on an existing subscription. Checking the state of associated data in an external system for example. The validate migration parameters look something like this:

```python
    params = dict(
        name="validate_node_enrollment",
        target="SYSTEM",
        description="Validate Node Enrollment before production",
        tag="NodeEnrollment",
        search_phrase="Node Enrollment%",
    )
```

It uses a `target` of `SYSTEM` - similar to how tasks are defined. That target is more of a free form sort of thing. Same thing with the `name` - that's the name of the actual workflow, and the `tag` is shared by of this set of workflows.

Generally the steps raise assertions if a check fails, otherwise return OK to the state:

```python
@step("Check NSO")
def check_nso(subscription: NodeEnrollment, node_name: str) -> State:
    device = get_device(device_name=node_name)

    if device is None:
        raise AssertionError(f"Device not found in NSO")
    return {"check_nso": "OK"}
```

## Modify

Very similar to validate but the migration params vary as one would expect with a different `target`:

```python
    params_modify = dict(
        name="modify_node_enrollment",
        target="MODIFY",
        description="Modify Node Enrollment",
        tag="NodeEnrollment",
        search_phrase="Node Enrollment%"
)
```

It would make any desired changes to the existing subscription and if need by, change the lifecycle state at the end. For example, for our `CREATE` that put the initial sub into the state `PROVISIONING`, a secondary modify workflow will put it into production and then set the state to `ACTIVE` at the end:

```python
@step("Activate Subscription")
def update_subscription_and_description(subscription: NodeEnrollmentProvisioning, node_name: str) -> State:
    subscription = change_lifecycle(subscription, SubscriptionLifecycle.ACTIVE)
    subscription.description = f"Node {node_name} Production"

    return {"subscription": subscription}
```

These also have the subscription id passed in in the initial step as outlined above.

## Terminate

Terminates a workflow and undoes changes that were made.

The migration params are as one would suspect:

```python
    params = dict(
        name="terminate_node_enrollment",
        target="TERMINATE",
        description="Terminate Node Enrollment subscription",
        tag="NodeEnrollment",
        search_phrase="Node Enrollment%",
    )
```

`target` is `TERMINATE`, `name` and `tag` are as you would expect.

The first step of these workflow are slightly different as it pulls in the `State` object rather than just the subscription id:

```python
@step("Load relevant subscription information")
def load_subscription_info(state: State) -> FormGenerator:
    subscription = state["subscription"]
    node = get_detailed_node(subscription["ne"]["esdb_node_id"])
    return {"subscription": subscription, "node_name": node.get("name")}
```

## Default Workflows

A Default Workflows mechanism is provided to provide a way for a given workflow to be automatically attached to all Products. To ensure this, modify the `DEFAULT_PRODUCT_WORKFLOWS` environment variable, and be sure to use `helpers.create()` in your migration.

Alternatively, be sure to execute `ensure_default_workflows()` within the migration if using `helpers.create()` is not desirable.

By default, `DEFAULT_PRODUCT_WORKFLOWS` is set to `['modify_note']`.
