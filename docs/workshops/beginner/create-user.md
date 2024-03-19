# Create User workflow

## Exercise 1: create User workflow

The create `User` workflow is very similar to the create `UserGroup` workflow,
the major difference is the increased number of user inputs needed to
initialize the subscription. This workflow uses the following steps:

```python
init
>> create_subscription
>> store_process_subscription(Target.CREATE)
>> initialize_subscription
>> provision_user
>> set_status(SubscriptionLifecycle.ACTIVE)
>> resync
>> done
```

There is one important difference though, one of the user inputs on the input
form is special: the selection of the user group the user belongs to. It is not
just an integer or a string, but the user must be able to select a user group
out of a list of already provisioned user groups. For this the database will be
queried to obtain a list of active user group subscriptions, and a special
input field type is used to display a dropdown input field on the input form.

In the orchestrator, all access to the database is implemented using
SQLAlchemy, and queries can be formulated using the classes from
`orchestrator.db.models` that map to the tables in the database. The following
query is all that is needed to get a list of `active` `UserGroup`
subscriptions:

```python
from orchestrator.db import db
from orchestrator.db.models import ProductTable, SubscriptionTable
from sqlalchemy import select

...

stmt = (
    select(SubscriptionTable)
    .join(ProductTable)
    .filter(ProductTable.product_type == "UserGroup", SubscriptionTable.status == "active")
    .with_only_columns(SubscriptionTable.subscription_id, SubscriptionTable.description)
)

subscriptions = db.session.scalars(stmt)

...
```

The `orchestrator.forms.validators` package provides a standard input component
called `choice_list` that will create the indicated enumeration and expects an
iterator that returns tuples containing a label and a value. The iterator is
created making use of the standard Python `zip` function. This input component
will show a dropdown with all labels and returns a list of associated chosen
keys.  The amount of entries that may be chosen is controlled by the
`min_items` and `max_items` arguments.

Putting everything together, the user group selector looks like this:

```python
from orchestrator.db import db
from orchestrator.db.models import ProductTable, SubscriptionTable
from sqlalchemy import select

def user_group_selector() -> list:
    user_group_subscriptions = {}
    stmt = (
        select(SubscriptionTable).join(ProductTable)
        .filter(ProductTable.product_type == "Port", SubscriptionTable.status == "active")
        .with_only_columns(SubscriptionTable.subscription_id, SubscriptionTable.description)
    )

    for user_group_id, user_group_description in db.session.execute(stmt).all():
        user_group_subscriptions[str(user_group_id)] = user_group_description

    return choice_list(
        Choice("UserGroupEnum", zip(user_group_subscriptions.keys(), user_group_subscriptions.items())),
        min_items=1,
        max_items=1,
    )
```

And can now be used in the input form as follows:

```python
user_group_ids: user_group_selector()
```

In the subscription initialization step the `group` resource type of the
`UserBlock` product block is assigned with the the `UserGroupBlock` from the
`UserGroup` subscription:

```python
subscription.user.group = UserGroup.from_subscription(user_group_ids[0]).user_group
```

Use the skeleton below to create the file `workflows/user/create_user.py`:

```python
from typing import List, Optional
from uuid import uuid4

from orchestrator.db.models import ProductTable, SubscriptionTable
from orchestrator.forms import FormPage
from orchestrator.forms.validators import Choice, choice_list
from orchestrator.targets import Target
from orchestrator.types import FormGenerator, State, SubscriptionLifecycle, UUIDstr
from orchestrator.workflow import done, init, step, workflow
from orchestrator.workflows.steps import resync, set_status, store_process_subscription
from orchestrator.workflows.utils import wrap_create_initial_input_form

from products.product_types.user import UserInactive, UserProvisioning
from products.product_types.user_group import UserGroup

# user group selector
...

# initial input form generator
...

# create subscription step
...

# initialize subscription step
...

# provision user step
...

# create user workflow
...
```

**Spoiler**: for inspiration look at an example implementation of the [user
create workflow ](https://github.com/workfloworchestrator/example-orchestrator-beginner/blob/main/workflows/user/create_user.py)
