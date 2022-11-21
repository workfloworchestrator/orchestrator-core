# Introduction

The workflow engine is the core of the orchestrator, it is responsible for the
following functions:

* Safely and reliable manipulate customer Subscriptions from one state to the
  next and maintain auditability.

* Create an API through which Subscriptions can be manipulated programmatically.

* Execute step functions in order and allow the retry of previously failed
  process-steps in an idempotent way.

* Atomically execute workflow functions.

A workflow is the combination of an initial input form, used to acquire input
from the user, and a list of workflow steps. Four types of workflows are
distinguished: `CREATE` workflows that will produce a subscription on a product
for a specific customer, `MODIFY` workflows to manipulate existing
subscriptions, `TERMINATE` workflows to end the subscription on a product for a
customer, and `SYSTEM` workflows that run scheduled and do not have an input
form. The latter type of workflows is also referred to as tasks, and can for
example be used to validate subscriptions against external operations 
support systems (OSS) and business support systems (BSS). The
same workflow step can be used in multiple workflows, and a set of workflow
steps can be combined in a step list and can be reused as well.  

Ideally workflow steps are idempotent. In case a workflow step fails, this
allows for save retry functionality without possible unwanted side effects or
new failures. This is especially important when a step is used to communicate
with external OSS and BSS. But in practice it will not always be possible to
make a step one hundred percent idempotent, thus requiring manual intervention
before a step can be retried. Note that the workflow steps created in this
beginner workshop are not written with idempotency in mind. 

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
