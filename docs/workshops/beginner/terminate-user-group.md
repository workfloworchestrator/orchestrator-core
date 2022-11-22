# Terminate UserGroup workflow

## Exercise 1: terminate UserGroup workflow

The terminate workflow is intended to end an subscription on a product for a
customer, releasing all provisioned resources.  The terminate workflow for the
`UserGroup` product uses the following steps:

```python
init
>> store_process_subscription(Target.TERMINATE)
>> unsync
>> deprovision_user_group
>> set_status(SubscriptionLifecycle.TERMINATED)
>> resync
>> done
```

All builtin steps used here were already discussed and follow the same pattern,
record the workflow process that was started for this subscription with
`store_process_subscription`, and protect the steps that modify the
subscription and/or OSS and BSS with `unsync` and `resync`. The only extra
builtin step used in the terminate worfklow is `set_status` to set the
subscription lifecycle state to`TERMINATED`.

The only task for the custom step `deprovision_user_group` is to deprovision
the user group from the imaginary group provisioning system.

Also no new or changed input is needed for this workflow, instead the input
form is used to ask the user if he/she really wants to terminate the
subscription. This is done by using a `Label` to show a question on the input
form:

```python
from orchestrator.forms.validators import Label

...
    class TerminateForm(FormPage):
        are_you_sure: Label = f"Are you sure you want to remove {subscription.description}?"
...
```

Remember that you can use the standard product method `from_subscription()` to
fetch the subscription from the database.

Besides the question if the user really wants to terminate the subscription,
only the Cancel and Submit button are shown on the input form. If the user
clicks the Cancel button then the terminate workflow is not started, so nothing
really happens. If the user clicks the Submit button then the terminate
workflow is started and will execute all steps that in the end will result in a
terminated subscription. Note that none of the workflow steps is using user
input from the `State` because there was no user input given.

Use the skeleton below to create the file
`workflows/user_group/terminate_user_group.py`:

```python
from orchestrator.forms import FormPage
from orchestrator.forms.validators import Label
from orchestrator.targets import Target
from orchestrator.types import InputForm, State, SubscriptionLifecycle, UUIDstr
from orchestrator.workflow import done, init, step, workflow
from orchestrator.workflows.steps import resync, set_status, store_process_subscription, unsync
from orchestrator.workflows.utils import wrap_modify_initial_input_form

from products import UserGroup

# initial input form generator
...

# deprovision user group step
...

# terminate user group workflow
...
```

**Spoiler**: for inspiration look at an example implementation of the [user
group terminate workflow ](https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/workflows/user_group/terminate_user_group.py)
