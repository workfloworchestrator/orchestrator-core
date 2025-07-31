# Introduction

A workflow is the combination of an initial input form, used to acquire input from the user, and a list of workflow steps.
[read more detailed explanation on workflows here](../../architecture/application/workflow.md)

The `workflow` decorator takes a description, initial input form, and a target
as input and turns a function into a workflow that returns a step list to be
executed by the workflow engine in a workflow process. A minimal workflow looks
like this:

```python
@workflow(
    "Create product subscription",
    initial_input_form=initial_input_form_generator,
    target=Target.CREATE,
)
def create_product_subscription():
    return init >> create_subscription >> done
```

Information between workflow steps is passed using `State`, which is nothing
more than a collection of key/value pairs, in Python represented by a `Dict`,
with string keys and arbitrary values. Between steps the `State` is serialized
to JSON and stored in the database. The `step` decorator is used to turn a
function into a workflow step, all arguments to the step function will
automatically be initialised with the value from the matching key in the
`State`. In turn the step function will return a `Dict` of new and/or modified
key/value pairs that will be merged into the `State` to be consumed by the next
step. The serialization and deserialization between JSON and the indicated
Python types is done automatically. A minimal workflow step looks as follows:

```python
@step("Create subscription")
def create_subscription(
    product: UUIDstr,
    user_input: str,
) -> State:
    subscription = build_subscription(product, user_input)
    return {"subscription": subscription}
```

The `product` and `user_input` arguments are filled from the corresponding
key/value pairs in the `State`, and the new `subscription` key/value is added
to the state to be used by one of the following steps.

Every workflow starts with the builtin step `init` and ends with the builtin
step `done`, with an arbitrary list of other builtin steps or custom steps in
between.
