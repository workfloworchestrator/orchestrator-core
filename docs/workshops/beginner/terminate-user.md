# Terminate User workflow

## Exercise 1: terminate User workflow

Nothing more needs to be explained at this stage, the terminate user workflow
is almost identical to the terminate user group workflow. As a reminder, and
for completeness, the terminate workflow for the `User` product uses  following
steps:

```python
init
>> store_process_subscription()
>> unsync
>> deprovision_user
>> set_status(SubscriptionLifecycle.TERMINATED)
>> resync
>> done
```

Use the skeleton below to create the file `workflows/user/terminate_user.py`:

```python
from orchestrator.core.forms import FormPage
from orchestrator.core.forms.validators import Label
from orchestrator.core.targets import Target
from orchestrator.core.types import InputForm, SubscriptionLifecycle, UUIDstr
from orchestrator.core.workflow import done, init, step, workflow
from orchestrator.core.workflows.steps import resync, set_status, store_process_subscription, unsync
from orchestrator.core.workflows.utils import wrap_modify_initial_input_form

from products import User

# initial input form generator
...

# deprovision user step
...

# terminate user workflow
...
```

**Spoiler**: for inspiration look at an example implementation of the [user
terminate workflow ](https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/workflows/user/terminate_user.py)
