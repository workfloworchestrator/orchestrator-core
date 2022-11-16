# Input forms

## Introduction

The orchestrator GUI is a ReactJS application that runs in front of the
orchestrator. It will consume the orchestrator API and enable the user to
interact with the products, subscriptions and processes that are built and run
in the orchestrator.

The GUI uses [Elastic-UI](https://elastic.github.io/eui/#/) as framework for
standard components and [Uniforms](https://uniforms.tools/) to parse
JSON-Schema produced by the forms endpoints in the core and render the correct
components and widgets.

## Input form generator

An input form generator function is needed to define the fields and the type of
the fields to be shown in the GUI to allow the user to input information needed
to instantiate a subscription based on a product. A simple input form generator
function looks as follows:

```python
def initial_input_form_generator(product_name: str) -> FormGenerator:
    class CreateProductForm(FormPage):
        class Config:
            title = product_name

        user_input: str

    form_input = yield CreateProductForm

    return form_input.dict()
```

All forms use `FormPage` as base and can be extended with the form input fields
needed. In this case a text input field will be shown, the text entered will be
assigned to `user_input`. All inputs from all input fields are then returned as
a `Dict` and will be merged into the `State`. The `product_name` argument comes
from the initial state. 

The optional `Config` class can be used to pass configuration information to
Uniforms. In this case Uniforms is asked to show a input form page with the
name of the product as title.

The helper functions `wrap_create_initial_input_form`, for create workflows,
and `wrap_modify_initial_input_form`, for modify and terminate workflows, are
used to integrate the input form into the workflow and handle all needed
`State` management. A common pattern used is:

```python
@workflow(
    "Create product subscription",
    initial_input_form=wrap_create_initial_input_form(initial_input_form_generator),
    target=Target.CREATE,
)
def create_product_subscription():
    return init >> create_subscription >> done
```


Looking at the `State`, for a create workflow it functionally works like this:

```text
+----------------------------+
|      workflow start        |
+----------------------------+
              |
           product
        product_name
              |
              V
+----------------------------+
|       input form(s)        |
+----------------------------+
              |
           product
        product_name
          user_input
              |
              V
+----------------------------+
|      create workflow       |
+----------------------------+
```

And for a modify and terminate workflows:

```text
+----------------------------+
|      workflow start        |
+----------------------------+
              |
           product
         organisation
       subscription_id
              |
              V
+----------------------------+
|       input form(s)        |
+----------------------------+
              |
           product
         organisation
       subscription_id
          user_input
              |
              V
+----------------------------+
| modify/terminate workflow  |
+----------------------------+
```
