# Form input logic

In the orchestrator core, form input elements are now class based and subclass the `FormPage` class in the core.

```python
from orchestrator.forms import FormPage, ReadOnlyField
```

And the validators module exposes validators that also function as "input type widgets":

```python
from orchestrator.forms.validators import CustomerId, choice_list, Choice
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

    customer_id: CustomerId = ReadOnlyField(CustomerId(ESNET_ORG_UUID))
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

    customer_id: CustomerId
    contact_persons: ContactPersonList = []  # type: ignore
    ticket_id: JiraTicketId = ""  # type: ignore
    service_ports: ListOfTwo[ServicePort]  # type: ignore
    service_speed: bandwidth("service_ports")  # type: ignore # noqa: F821
    speed_policer: bool = False
    remote_port_shutdown: bool = True
```

### Multi step form input

Similar to the original "list based" form `Input` elements, to do a multistep form flow yield multiple times and then combine the results at the end:

```python
def initial_input_form_generator(product: UUIDstr, product_name: str) -> FormGenerator:
    class CreateNodeForm(FormPage):
        class Config:
            title = product_name

        customer_id: CustomerId = ReadOnlyField(CustomerId(SURFNET_NETWORK_UUID))
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

## custom form field

You can create a custom field component in the frontend. The components in `orchestrator-gui/src/lib/uniforms-surfnet/src` can be used to study reference implementations for a couple of custom form field types.

For it to show up in the form, you have to do 2 things, a pydantic type/class in the backend and add the component to the `AutoFieldLoader.tsx`.

as an example I will create a custom field with name field and group select field.

### pydantic type/class in backend

Create a pydantic type/class.

``` python
from uuid import UUID


class ChooseUser(str):
    group_id: UUID  # type:ignore

    @classmethod
    def __modify_schema__(cls, field_schema: dict[str, Any]) -> None:
        uniforms: dict[str, Any] = {}

        if cls.group_id:
            uniforms["groupId"] = cls.group_id

        field_schema.update(format="ChooseUser", uniforms=uniforms)
```

And add it to a form:

``` python
def initial_input_form_generator(product: UUIDstr, product_name: str) -> FormGenerator:
    class ChoseUserForm(FormPage):
        class Config:
            title = product_name

        user: ChooseUser

    user_input = yield ChoseUserForm
```

To prefill the user_id, you need to add the value to the prop, for prefilling the group_id you need to create a new class:

```python
def user_choice(group_id: int | None = None) -> type:
    namespace = {"group_id": group_id}
    return new_class(
        "ChooseUserValue", (ChooseUser,), {}, lambda ns: ns.update(namespace)
    )


def initial_input_form_generator(product: UUIDstr, product_name: str) -> FormGenerator:
    class ChoseUserForm(FormPage):
        class Config:
            title = product_name

        user: user_choice("group_id_1") = "user_id_1"

    user_input = yield ChoseUserForm
```

### auto field loader

The auto field loader is for loading the correct field component in the form.
It has switches that check the field type and the field format.
You have to add your new form field here.

for this example, we would need to add to a `ChooseUser` case to the String switch:

```js
...
import ChooseUserField from "custom/uniforms/ChooseUserField";

export function autoFieldFunction(props: GuaranteedProps<unknown> & Record<string, any>, uniforms: Context<unknown>) {
    const { allowedValues, checkboxes, fieldType, field } = props;
    const { format } = field;

    switch (fieldType) {
        ...
        case String:
            switch (format) {
               ...
                case "ChooseUser":
                    return ChooseUserField;
            }
            break;
    }

    ...
}

```

### custom field example

example custom field to select a user by group.

``` js
import { EuiFlexItem, EuiFormRow, EuiText } from "@elastic/eui";
import { FieldProps } from "lib/uniforms-surfnet/src/types";
import React, { useCallback, useContext, useEffect, useState } from "react";
import { WrappedComponentProps, injectIntl } from "react-intl";
import ReactSelect, { SingleValue } from "react-select";
import { getReactSelectTheme } from "stylesheets/emotion/utils";
import { connectField, filterDOMProps } from "uniforms";
import ApplicationContext from "utils/ApplicationContext";
import { Option } from "utils/types";
import { css } from "@emotion/core";

export const ChoosePersonFieldStyling = css`
    section.group-user {
        display: flex;
        flex-direction: row;
        flex-wrap: wrap;

        div.group-select {
            width: 50%;
        }
        div.user-select {
            width: 50%;
            padding-left: 5px;
        }
    }
`;

interface Group {
    id: string;
    name: string;
}

interface User {
    id: string;
    name: string;
    age: number;
}


export type ChooseUserFieldProps = FieldProps<
    string,
    {
        groupId?: string;
    } & WrappedComponentProps
>;

const groupToOption = (group: Group): Option => {
    return {
        value: group.id,
        label: `${group.id.substring(0, 8)} ${group.name}`,
    };
}

const userToOption = (user: User): Option => {
    return {
        value: user.id,
        label: `${user.name} (${user.age})`,
    };
}

declare module "uniforms" {
    interface FilterDOMProps {
        groupId: never;
    }
}
filterDOMProps.register("groupId");

function ChoosePerson({
    id,
    name,
    label,
    description,
    onChange,
    value,
    disabled,
    placeholder,
    readOnly,
    error,
    showInlineError,
    errorMessage,
    groupId,
    intl,
    ...props
}: ChooseUserFieldProps) {
    const { apiClient, customApiClient, theme } = useContext(ApplicationContext);

    const [groups, setGroups] = useState<Group[]>([]);
    const [selectedGroupId, setGroupId] = useState<number | string | undefined>(groupId);
    const [users, setUsers] = useState<User[]>([]);
    const [loading, setLoading] = useState(true);

    const onChangeGroup = useCallback(
        (option: SingleValue<Option>) => {
            let value = option?.value;
            if (value === undefined) return;

            setLoading(true);
            setGroupId(value);
            setUsers([]);

            // do api call to get users by group id and set users with the fetched data.
            setTimeout(() => {
                let users = [{ id: "user_id_1", name: "user 1", age: 25 }, { id: "user_id_2", name: "user 2", age: 30 }]
                if (value == "group_id_2") {
                    users = [{ id: "user_id_3", name: "user 3", age: 35 }]
                } else if (value == "group_id_3") {
                    users = [{ id: "user_id_4", name: "user 4", age: 40 }, { id: "user_id_5", name: "user 5", age: 45 }]
                }
                setUsers(users)
                setLoading(false);
            }, 1000)
        },
        [customApiClient]
    );

    useEffect(() => {
        setLoading(true);

        // do api call to get groups for the first select.

        setTimeout(() => {
            setGroups([
                { id: "group_id_1", name: "group 1" },
                { id: "group_id_2", name: "group 2" },
                { id: "group_id_3", name: "group 3" }
            ]);
            setLoading(false);

            if (groupId) {
                onChangeGroup({ value: groupId } as Option);
            }
        }, 1000)
    }, [onChangeGroup, apiClient, groupId]);

    // use i18n translations.
    const groupsPlaceholder = loading ? "Loading..." : "Select a group";
    const userPlaceholder = loading ? "Loading..." : selectedGroupId ? "Select a user" : "Select a group first";

    const group_options: Option[] = (groups as Group[])
        .map(groupToOption)
        .sort((x, y) => x.label.localeCompare(y.label));
    const group_value = group_options.find((option) => option.value === selectedGroupId?.toString());

    const user_options: Option<string>[] = users
        .map(userToOption)
        .sort((x, y) => x.label.localeCompare(y.label));
    const user_value = user_options.find((option) => option.value === value);

    const customStyles = getReactSelectTheme(theme);

    return (
        <EuiFlexItem css={ChoosePersonFieldStyling}>
            <section {...filterDOMProps(props)}>
                <EuiFormRow
                    label={label}
                    labelAppend={<EuiText size="m">{description}</EuiText>}
                    error={showInlineError ? errorMessage : false}
                    isInvalid={error}
                    id={id}
                    fullWidth
                >
                    <section className="group-user">
                        <div className="group-select">
                            <EuiFormRow label="Group" id={`${id}.group`} fullWidth>
                                <ReactSelect<Option, false>
                                    inputId={`${id}.group.search`}
                                    name={`${name}.group`}
                                    onChange={onChangeGroup}
                                    options={group_options}
                                    placeholder={groupsPlaceholder}
                                    value={group_value}
                                    isSearchable={true}
                                    isDisabled={disabled || readOnly || groups.length === 0}
                                    styles={customStyles}
                                />
                            </EuiFormRow>
                        </div>
                        <div className="user-select">
                            <EuiFormRow label="User" id={id} fullWidth>
                                <ReactSelect<Option<string>, false>
                                    inputId={`${id}.search`}
                                    name={name}
                                    onChange={(selected) => {
                                        onChange(selected?.value);
                                    }}
                                    options={user_options}
                                    placeholder={userPlaceholder}
                                    value={user_value}
                                    isSearchable={true}
                                    isDisabled={disabled || readOnly || users.length === 0}
                                    styles={customStyles}
                                />
                            </EuiFormRow>
                        </div>
                    </section>
                </EuiFormRow>
            </section>
        </EuiFlexItem>
    );
}

export default connectField(injectIntl(ChoosePerson), { kind: "leaf" });
```

## TBA
