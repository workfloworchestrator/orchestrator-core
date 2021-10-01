# Step 4 - Create a domain mnodel

To manipulate a subscription and to make use of the Typing of Pydantic in the workflows we define so-called `Domain-Models.`
This construct enables the user to use the `dot` notation to interact with a subscription like it is a class.

Read the [Domain Models](../../../architecture/application/domainmodels) section to understand how the concept works.

### Exercise -  Create a domain model
The domain model is correctly implemented when it achieves the following goals:

- It must implement the life-cycles: `Inintial` and `Active`
- It must be possible to create an Subscription in the database through the domain model.
- Make use of `.save()`, `.from_product()`, `from_lifecycle()` and `from_subscription()` methods to manipulate the subscription.

!!! tip
    Below you can find some hints towards the answers

    - Take a look at the tests `conftest.py` to see how a domain model can be declared
    - The Product migration must be setup corretly
    - The Domain model needs to be registered in the product block model registry.
    - You must create an `is_base` model.
