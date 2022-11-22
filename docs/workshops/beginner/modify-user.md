# Modify User workflow

## Exercise 1: modify User workflow

The modify `User` workflow is also very similar to the modify `UserGroup`
workflow, except for the different set of resource types that can be changed.
This workflow uses the following steps: 

```python
init
>> store_process_subscription(Target.MODIFY)
>> unsync
>> modify_user_subscription
>> resync
>> done
```

To show the current user group in the dropdown on the input form, the
subscription ID of that user group is needed. But the `User` subscription only
contains a reference to the `UserGroupBlock`, not the `UserGroup` subscription
that is needed. Luckily, every instantiated product block has an attribute
`owner_subscription_id` that contains the subscription ID of the subscription
owning this product block instance.

The `choice_list` input both returns a list as result and expects a list of
values that it uses to display the currently selected item(s). The following
will display a dropdown showing the currently selected user group: 

```python
user_group_id: user_group_selector() = [str(subscription.user.group.owner_subscription_id)]
```

Use the skeleton below to create the file `workflows/user/modify_user.py`, and
note that the `user_group_selector` from the create workflow is being reused:

```python
from typing import List, Optional

from orchestrator.forms import FormPage
from orchestrator.targets import Target
from orchestrator.types import FormGenerator, State, UUIDstr
from orchestrator.workflow import done, init, step, workflow
from orchestrator.workflows.steps import resync, store_process_subscription, unsync
from orchestrator.workflows.utils import wrap_modify_initial_input_form

from products.product_types.user import User
from products.product_types.user_group import UserGroup
from workflows.user.create_user import user_group_selector

# initial input form generator
...

# modify user step
...

# modify user workflow
...
```

**Spoiler**: for inspiration look at an example implementation of the [user
modfiy workflow ](https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/workflows/user/modify_user.py)
