# Create UserGroup workflow

## Exercise 1: create UserGroup workflow

The create workflow will produce a subscription for a specific customer on the
UserGroup product. This is done by executing the following workflow steps:

```python
init
>> create_subscription
>> store_process_subscription(Target.CREATE)
>> initialize_subscription
>> provision_user_group
>> set_status(SubscriptionLifecycle.ACTIVE)
>> resync
>> done
```

The builtin steps `init` and `done` are always part of a workflow and mark the
begin and end of the workflow. Three other builtin steps are being used here
that are almost always part of a create workflow:

*   **store_process_subscription** 

    The orchestrator executes a workflow in a process, and keeps track of all
    workflows that have been run to create, modify or terminate a subscription,
    so there is an administrative trail of what happened to each subscription
    and when.  This step is used to enter this information into the database.
    The argument `Target.CREATE` indicates that this is a create workflow. The
    reason that this step is not the first step directly after `init` is
    because we need to know the subscription ID that is not yet known at that
    point in the workflow.

*   **set_status**

    At the end of the workflow, after the subscription has been created, and
    the interaction with all OSS and BSS was successfully finished, the
    subscription state is set to `SubscriptionLifecycle.ACTIVE`. From this
    moment on the modify and terminate workflows can be started on this
    subscription.

*   **resync**

    Every subscription has a notion of being in sync or not with all OSS and
    BSS. There are several moments that a subscription is deemed to be out of
    sync, one is during the time a workflow is active for a subscription,
    another is when a validation workflow (will be explained in the advanced
    workshop) has detected a discrepancy between the subscription and any of
    the OSS or BSS. One important side effect of a subscription being out of
    sync is that no new workflows can be started for that subscription, this is
    to protect for actions being taken on information that is possibly not
    accurate. The `resync` step sets the subscription in sync.

The three remaining steps are custom to this workflow:

*   **create_subscription**

    This step will create a new virgin subscription on a product. Every product
    has the standard method `from_product_id()` that takes two mandatory
    arguments: `product_id` and `customer_id`. Use this method on the
    `UserGroupInactive` product to create a subscription in state
    `SubscriptionLifecycle.INITIAL`. Because there is no CRM used during this
    beginner workshop the customer UUID can be faked.

    Make sure that this step returns a `Dict` with at least the keys
    `'subscription'` and `'subscription_id'` to make the orchestrator merge
    these keys into the workflow `State`. When leaving a step the orchestrator
    will also automatically commit the `'subscription'` to the database. The
    `'subscription_id'` key is needed by the `store_process_subscription` step.

*   **initialize_subscription**

    This step will initialize the resource types based on the input from the
    user. In this case only the name of the group needs to be assigned. Also
    set the subscription description to something meaningful at this stage.
    After this, the subscription can be transitioned to
    `SubscriptionLifecycle.PROVISIONING`, this will trigger checks to make sure
    that all mandatory resource types are present for that lifecycle state.
    Every product has the standard method `from_other_lifecycle()` to
    accomplish this, this method takes the original subscription and the targe
    lifecycle state as arguments.

    Make sure that this step returns a `Dict` with also at least the key
    `'subscription'` to merge the modified subscription into the workflow state
    and have the orchestrator commit the subscription changes to the database.

*  **provision_user_group**

    Now the user group can be provisioned in all OSS and BSS as necessary.  As
    there is no actual user group provisioning system during this workshop,
    this interaction is being faked. The returned (fake) group ID is assigned
    to the intended resource type.

    Yet again make sure that this step returns a `Dict` with at least the key
    `'subscription'`.

The only thing left that is needed is an initial input form generator function
with one string input field to ask the user for the name of the user group.

Use the skeleton below to create the file
`workflows/user_group/create_user_group.py`:

```python
from uuid import uuid4

from orchestrator.forms import FormPage
from orchestrator.targets import Target
from orchestrator.types import FormGenerator, State, SubscriptionLifecycle, UUIDstr
from orchestrator.workflow import done, init, step, workflow
from orchestrator.workflows.steps import resync, set_status, store_process_subscription
from orchestrator.workflows.utils import wrap_create_initial_input_form

from products.product_types.user_group import UserGroupInactive, UserGroupProvisioning

# initial input form generator
...

# create subscription step
...

# initialize subscription step
...

# provision user group step
...

# create user group workflow
...
```

**Spoiler**: for inspiration look at an example implementation of the [user
group create workflow ](https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/workflows/user_group/create_user_group.py)


