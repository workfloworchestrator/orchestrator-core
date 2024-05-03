# Forms - from a frontend perspective

Orchestrator Core contains a module called Pydantic Forms. Pydantic Forms allows for configuration of input forms to collect user input needed for the execution of a workflow. The module contains a frontend part that displays the forms automatically and handles submission and showing validation errors. This documentation describes what happens on the frontend side of this process.

## Initiating a workflow from frontend

A workflow can be initiated by doing a POST call to ''/processes/<workflow_name>''

The steps that happen to initiate a workflow on the frontend are:

-   A `POST` request to `/processes/<workflow_name>` with an empty payload
-   The backend determines what input values are missing and sends a response with http status code `510` and a payload containing a [JSON6Schema definition][2] describing the form to display. See [Example JSON6Schema response](#example-json6schema-response)
-   The frontend uses the [Uniforms library][1] to parse the JSON response into a form to display
-   The [AutofieldLoader function][3] is called for each of the form.properties in the JSON response. This function uses the properties `type` and `format` to determine what kind of field will be displayed.

```

In the example json response below one of the properties is
...
            "customer_id": {
                "default": "c9b5e717-0b11-e511-80d0-005056956c1a",
                "format": "customerId",
                "title": "Customer Id",
                "type": "string",
                "uniforms": {
                    "disabled": true,
                    "value": "c9b5e717-0b11-e511-80d0-005056956c1a"
                }
            }
...

In the autoFieldFunction this maps to a CustomerField.

export function autoFieldFunction(
    props,
    uniforms,
) {
    const { allowedValues, checkboxes, fieldType, field } = props;
    const { format } = field;

    switch (fieldType) {
    ...
        case String:
            switch (format) {
                ....
                case 'customerId':
                    return CustomerField;
                ...
            }
    ...

The CustomerField is a React component that is provided by the Orchestrator Component Library.
It's passed the complete property object so it can use them to adjust it's behavior.
```

-   A `POST` with the form values is made to the same `/processes/<workflow_name>` endpoint
-   The response status code can be:
    -   `400: Form invalid` Invalid values have been detected because the validators the backend runs have failed. An error message is shown.
    -   `510: FormNotComplete` There is another step. This response contains another json response containing a form.
    -   `201: Created` The workflow was initiated successfully. The response contains a workflow id and the user is redirected to the workflow detail page

**Note**. For forms that have multiple steps the user input for each step is accumulated in local frontend state and posted to `/processes/<workflowname>` on each step. The endpoint will receive all available user inputs on each step and determine what other user input it still needs or if it's ready to start the workflow.

**Note 2** The Orchestrator Component library contains fields that are marked as deprecated and live in a folder named `deprecated`. These contain field types that are very specific to workflows that are in use by SURF. There are plans to remove these from the general purpose components library.

**Note 3** There are plans to make it easier to extend this functionality to add custom field types and extend the switch statement in the autoFieldFunction to include these custom `types` or `formats`

## Backend: Creating a workflow that generates a form that asks for user input

Creating workflows is described in other parts of this documentation in more detail. The practical steps and those that are relevant to the frontend
are these

-   A mapping between a function and a `processes/<workflow-name>` endpoint is added to the `workflows/init.py` file

```
    `LazyWorkflowInstance("surf.workflows.core_link.create_core_link", "create_core_link")`
```

This makes `POST` requests to `processes/create_core_link` call surf.core_lint.create_core_link with the `POST` payload

-   The create_core_link function is decorated with the create_workflow decorator. It provides workflow orchestrator functionality.

```
@create_workflow("Create Core Link", initial_input_form=initial_input_form_generator)
def create_core_link() -> StepList:
    return (
        begin
        >> step 1
        ...
        >> step last
    )
```

-   If the POST request contains no user_input the value provided to initial_input_form is called, in this case the function initial_input_form_generator

```
def initial_input_form_generator(product_name: str) -> FormGenerator:
    user_input = yield step_1_form(product_name)

    ....

    user_input_ports = yield step_2_form(product_name, ..)

    return (
        ... result from step ...
    )
```

-   The functionality provided by the workflow orchestrator decorator makes every yield statement pass if the required user input data is passed in or return a response to the client with a `510` status code and a payload containing the definition for the form to display in [JSON Schema 6 format](https://json-schema.org/draft-06/json-schema-release-notes)

-   An example of what the _step_1_form_ function could look like.

```
def step_1_form(product_name: str) -> type[FormPage]:
    class SpeedChoice(Choice):
        _10000 = ("10000", "10 Gbps")
        _40000 = ("40000", "40 Gbps")
        _100000 = ("100000", "100 Gbps")
        _400000 = ("400000", "400 Gbps")

    class CreateCoreLinkSpeedForm(FormPage):
        model_config = ConfigDict(title=product_name)

        organisation: SurfnetOrganisation

        label_corelink_settings: Label
        divider_1: Divider

        corelink_service_speed: SpeedChoice = SpeedChoice._400000
        isis_metric: IsisMetric = 20

    return CreateCoreLinkSpeedForm
```

The type specified for each property (eg divider_1: Divider) determines what `type` property it gets in the resulting JSON 6 Schema. There are a set number of property types that can be provided and that are automatically handled by the frontend by default. This is extendable. [TODO: Insert complete list of possible types]

-   The response for a POST call without user input to _<wfo-url>/processes/create_core_link_ is

## Example JSON6Schema response:

```
{
    "type": "FormNotCompleteError",
    "detail": [not relevant]
    "traceback": [not relevant]
    "form": {
        "$defs": {
            "SpeedChoice": {
                "enum": [
                    "10000",
                    "40000",
                    "100000",
                    "400000"
                ],
                "options": {
                    "10000": "10 Gbps",
                    "100000": "100 Gbps",
                    "40000": "40 Gbps",
                    "400000": "400 Gbps"
                },
                "title": "SpeedChoice",
                "type": "string"
            }
        },
        "additionalProperties": false,
        "properties": {
            "customer_id": {
                "default": "c9b5e717-0b11-e511-80d0-005056956c1a",
                "format": "customerId",
                "title": "Customer Id",
                "type": "string",
                "uniforms": {
                    "disabled": true,
                    "value": "c9b5e717-0b11-e511-80d0-005056956c1a"
                }
            },
            "label_corelink_settings": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": null,
                "format": "label",
                "title": "Label Corelink Settings",
                "type": "string"
            },
            "divider": {
                "anyOf": [
                    {
                        "type": "string"
                    },
                    {
                        "type": "null"
                    }
                ],
                "default": null,
                "format": "divider",
                "title": "Divider",
                "type": "string"
            },
            "corelink_service_speed": {
                "allOf": [
                    {
                        "$ref": "#/$defs/SpeedChoice"
                    }
                ],
                "default": "400000"
            },
            "isis_metric": {
                "default": 20,
                "maximum": 16777215,
                "minimum": 1,
                "title": "Isis Metric",
                "type": "integer"
            }
        },
        "title": "SN8 Corelink",
        "type": "object"
    },
    "title": [not relevant],
    "status": 510
}
```

[1]: (https://www.npmjs.com/package/uniforms)
[2]: (https://json-schema.org/draft-06/json-schema-release-notes)
[3]: (https://github.com/workfloworchestrator/orchestrator-ui-library/blob/main/packages/orchestrator-ui-components/src/components/WfoForms/AutoFieldLoader.tsx)
