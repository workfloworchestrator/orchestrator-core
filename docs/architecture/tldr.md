# Architecture; TLDR

The architecture of how the orchestrator-core is setup can be split in two sections. The orchestration philosophy of how
workflows are setup and run, and how the application can be used to define products that can be subscribed to by customers.

## Application architecture

The Application extends a FastAPI application and therefore can make use of all the awesome features of FastAPI, pydantic
and asyncio python.

## Step Engine
At its core the Orchestrator workflow engine will execute a list of functions in order and store the result of each
function to the database. The Orchestrator is able to execute any list of functions that the user envisions so long as they
return a dictionary and/or consume variables stored in keys under that dictionary.

```python
@workflow("Name of the workflow", initial_input_form=input_form_generator)
def workflow():
    return (
        init
        >> arbitrary_step_func_1
        >> arbitrary_step_func_2
        >> arbitrary_step_func_3
        >> done
    )
```

The `@workflow` decorator converts what the function returns into a `StepList` which the engine executes sequentially.
If and when the step functions raise an exeption, the workflow will fail at that step and allow the user to retry.

## Products and Subscriptions
The second part of the orchestrator is a product database that allows a developer to define a collection of logically grouped
resources, that when filled in create a Subscription, given to a customer. The description of a product is done in the
`Product`, `FixedInput`, `ProductBlock` and `ResourceType` tables. When a workflow creates a subscription for a customer it creates
instances of a `Product`, `ProductBlock` and `ResourceType` and stores them as `Subscriptions`, `SubscriptionInstances`
and ``SubscriptionInstanceValues.`

It is therefore possible to have N number of Subscriptions to a single product. A workflow is typically executed
to manipulate a Subscription and transition it from one lifecycle state to another (`Initial`, `Provisioning`,
`Active`, `Terminated`).
