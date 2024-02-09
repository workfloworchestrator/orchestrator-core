from typing import Annotated

import structlog
from orchestrator.domain import SubscriptionModel
from orchestrator.forms import FormPage
from orchestrator.forms.validators import CustomerId, Divider
from orchestrator.types import FormGenerator, State, SubscriptionLifecycle, UUIDstr
from orchestrator.workflow import StepList, begin, step
from orchestrator.workflows.steps import set_status
from orchestrator.workflows.utils import modify_workflow
from pydantic import AfterValidator
from pydantic_forms.validators import ReadOnlyField

from products.product_blocks.example1 import ExampleStrEnum1
from products.product_types.example1 import Example1, Example1Provisioning
from workflows.example1.shared.forms import must_be_unused_to_change_mode_validator
from workflows.shared import modify_summary_form


def subscription_description(subscription: SubscriptionModel) -> str:
    """The suggested pattern is to implement a subscription service that generates a subscription specific
    description, in case that is not present the description will just be set to the product name.
    """
    return f"{subscription.product.name} subscription"


logger = structlog.get_logger(__name__)

validated_example_str_enum_1 = Annotated[ExampleStrEnum1, AfterValidator(must_be_unused_to_change_mode_validator)]


def initial_input_form_generator(subscription_id: UUIDstr) -> FormGenerator:
    subscription = Example1.from_subscription(subscription_id)
    example1 = subscription.example1

    # TODO fill in additional fields if needed

    class ModifyExample1Form(FormPage):
        customer_id: CustomerId = subscription.customer_id  # type: ignore

        divider_1: Divider

        unmodifiable_str: ReadOnlyField(example1.unmodifiable_str)
        annotated_int: ReadOnlyField(example1.annotated_int)
        example_str_enum_1: validated_example_str_enum_1 = example1.example_str_enum_1
        modifiable_boolean: bool = example1.modifiable_boolean
        always_optional_str: str | None = example1.always_optional_str

    user_input = yield ModifyExample1Form
    user_input_dict = user_input.dict()

    summary_fields = [
        "example_str_enum_1",
        "unmodifiable_str",
        "modifiable_boolean",
        "annotated_int",
        "always_optional_str",
    ]
    yield from modify_summary_form(user_input_dict, subscription.example1, summary_fields)

    return user_input_dict | {"subscription": subscription}


@step("Update subscription")
def update_subscription(
    subscription: Example1Provisioning,
    example_str_enum_1: ExampleStrEnum1,
    modifiable_boolean: bool,
    always_optional_str: str | None,
) -> State:
    # TODO: get all modified fields
    subscription.example1.example_str_enum_1 = example_str_enum_1
    subscription.example1.modifiable_boolean = modifiable_boolean
    subscription.example1.always_optional_str = always_optional_str

    return {"subscription": subscription}


@step("Update subscription description")
def update_subscription_description(subscription: Example1) -> State:
    subscription.description = subscription_description(subscription)
    return {"subscription": subscription}


additional_steps = begin


@modify_workflow("Modify example1", initial_input_form=initial_input_form_generator, additional_steps=additional_steps)
def modify_example1() -> StepList:
    return (
        begin
        >> set_status(SubscriptionLifecycle.PROVISIONING)
        >> update_subscription
        >> update_subscription_description
        # TODO add additional steps if needed
        >> set_status(SubscriptionLifecycle.ACTIVE)
    )
