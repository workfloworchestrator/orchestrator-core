# Modify UserGroup workflow

## Exercise 1: modify UserGroup workflow

The modify workflow can be used to change some or all of the resource types of
an existing subscription. In this case the following workflow steps will be
used:

```python
init
>> store_process_subscription(Target.MODIFY)
>> unsync
>> modify_user_group_subscription
>> resync
>> done
```

Besides the subscription administration that needs to be done, which probably
already starts to look familiar, there is only one custom step that needs to be
implemented. Most of the builtin steps were already discussed, but the `unsync`
step is new. As can be guessed, this step has the opposite effect as the
`resync` step, it sets an subscription out of sync for the duration of the
modify which prohibits other workflows being started for this subscription.

The `modify_user_group_subscription` step has three simple tasks. It will store
the changed name of the group in the resource type `user_group` of the
subscription. Secondly, it will change the subscription description to reflect
the changed user group name. And last but not least, the user group name is
also updated in the imaginary external user group provisioning system. Do not
forget to return a `Dict` with a key `'subscription'` to merge the updated
subscription into the workflow `State`, otherwise updates to the subscription
will also not be saved to the database.

The only thing remaining now is to create an initial input form generator that
will show an input form with a string input field that shows the existing user
group name, and allows for changes to be made. This is established by assigning
the existing value to the input field used to enter the user group name. And as
an extra, a second read-only field will be shown with the user group ID. For
the latter the forms helper function `ReadOnlyField` can be used in the
following way:

```python
group_id: int = ReadOnlyField(subscription.user_group.group_id)
```

But where does the instantiated subscription come from in the initial input
form generator? Remember that the workflow `State` available to the input form
does not include the `subscription`, it only has the `subscription_id` at that
stage. Luckily every product has a standard `from_subscription()` method that
takes an subscription ID as argument that will fetch the subscription from the
database and returns a fully instantiated domain model.  Remember to use the
`wrap_modify_initial_input_form` wrapper for this modify workflow to make the
subscription ID available to the input form.

Use the skeleton below to create the file
`workflows/user_group/modify_user_group.py`:

```python
from orchestrator.forms import FormPage, ReadOnlyField
from orchestrator.targets import Target
from orchestrator.types import FormGenerator, State, UUIDstr
from orchestrator.workflow import done, init, step, workflow
from orchestrator.workflows.steps import resync, store_process_subscription, unsync
from orchestrator.workflows.utils import wrap_modify_initial_input_form

from products.product_types.user_group import UserGroup

# initial input form generator
...

# modify user group step
...

# modify user group workflow
...
```

**Spoiler**: for inspiration look at an example implementation of the [user
group modfiy workflow ](https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/workflows/user_group/modify_user_group.py)
