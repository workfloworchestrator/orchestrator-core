# Form input logic

In the orchestrator core, form input elements are now class based and subclass the `FormPage` class in the core.

```python
from orchestrator.forms import FormPage, ReadOnlyField
```

And the validators module exposes validators that also function as "input type widgets":

```python
from orchestrator.forms.validators import OrganisationId, choice_list, Choice
```

It's worth poking around in that module to see the various input types the core library exposes.

## Form examples

Here is a relatively simple input form:

```python
equipment = get_planned_equipment()
choices = [f"{eq['name']}" for eq in equipment]

EquipmentList = choice_list(
    Choice("EquipmentEnum", zip(choices, choices)),
    min_items=1,
    max_items=1,
    unique_items=True,
)


class CreateNodeEnrollmentForm(FormPage):
    class Config:
        title = product_name

    organisation: OrganisationId = ReadOnlyField(OrganisationId(ESNET_ORG_UUID))
    select_node_choice: EquipmentList


# Don't call like this CreateNodeEnrollmentForm() or you'll
# get a vague error.
user_input = yield CreateNodeEnrollmentForm
```

It has a read only ORG ID and exposes a list of devices pulled from ESDB for the user to choose from.

### Choice widgets

Of note: `min_items` and `max_items` do not refer to the number of elements in the list. This UI construct allows for an arbitrary number of choices to be made - there are `+` and `-` options exposed in the UI allowing for multiple choices selected by the user. So `min 1 / max 1` tells the UI to display one pull down list of choices one of which must be selected, and additional choices can not be added.

If one defined something like `min 1 / max 3` it would display one pulldown box by default and expose a `+` element in the UI. The user could click on it to arbitrarily add a second or a third pulldown list. `min 0` would not display any list by default but the user could use `+` to add some, etc.

Since multiple choices are allowed, the results are returned as a list even if there is only a single choice element:

```python
eq_name = user_input.select_node_choice[0]
```

The `zip()` maneuver takes the list and makes it into a dict with the same keys and values. So the display text doesn't have to be the same as the value returned.

### Accept actions

Confirming actions is a common bit of functionality. This bit of code displays some read only NSO payload and lets the user ok the dry run:

```python
from orchestrator.forms import FormPage, ReadOnlyField
from orchestrator.forms.validators import Accept, LongText


def confirm_dry_run_results(dry_run_results: str) -> State:
    class ConfirmDryRun(FormPage):
        nso_dry_run_results: LongText = ReadOnlyField(dry_run_results)
        confirm_dry_run_results: Accept

    user_input = yield ConfirmDryRun

    return user_input
```

### Generic python types

It is possible to mix generic python types in the with the defined validation fields:

```python
class CreateLightPathForm(FormPage):
    class Config:
        title = product_name

    organisation: OrganisationId
    contact_persons: ContactPersonList = []  # type: ignore
    ticket_id: JiraTicketId = ""  # type: ignore
    service_ports: ListOfTwo[ServicePort]  # type: ignore
    service_speed: bandwidth("service_ports")  # type: ignore # noqa: F821
    speed_policer: bool = False
    remote_port_shutdown: bool = True
```

### Multi step form input

Similar to the original "list based" form `Input` elements, to do a multi step form flow yield multiple times and then combine the results at the end:

```python
def initial_input_form_generator(product: UUIDstr, product_name: str) -> FormGenerator:
    class CreateNodeForm(FormPage):
        class Config:
            title = product_name

        organisation: OrganisationId = ReadOnlyField(
            OrganisationId(SURFNET_NETWORK_UUID)
        )
        location_code: LocationCode
        ticket_id: JiraTicketId = ""  # type:ignore

    user_input = yield CreateNodeForm

    class NodeIdForm(FormPage):
        class Config:
            title = product_name

        ims_node_id: ims_node_id(
            user_input.location_code, node_status="PL"
        )  # type:ignore # noqa: F821

    user_input_node = yield NodeIdForm

    return {**user_input.dict(), **user_input_node.dict()}
```

## TBA
