from typing import Annotated

import structlog
from orchestrator.domain import SubscriptionModel
from orchestrator.forms import FormPage
from orchestrator.forms.validators import CustomerId, Divider, Label
from orchestrator.targets import Target
from orchestrator.types import SubscriptionLifecycle
from orchestrator.workflow import StepList, begin, step
from orchestrator.workflows.steps import store_process_subscription
from orchestrator.workflows.utils import create_workflow
from pydantic import AfterValidator, ConfigDict
from pydantic_forms.types import FormGenerator, State, UUIDstr

from products.product_blocks.example1 import AnnotatedInt, ExampleStrEnum1
from products.product_types.example1 import Example1Inactive, Example1Provisioning
from workflows.example1.shared.forms import (
    annotated_int_must_be_unique_validator,
    must_be_unused_to_change_mode_validator,
)
from workflows.shared import create_summary_form


def subscription_description(subscription: SubscriptionModel) -> str:
    """Generate subscription description.

    The suggested pattern is to implement a subscription service that generates a subscription specific
    description, in case that is not present the description will just be set to the product name.
    """
    return f"{subscription.product.name} subscription"


logger = structlog.get_logger(__name__)

validated_example_str_enum_1 = Annotated[ExampleStrEnum1, AfterValidator(must_be_unused_to_change_mode_validator)]
validated_annotated_int = Annotated[AnnotatedInt, AfterValidator(annotated_int_must_be_unique_validator)]


def initial_input_form_generator(product_name: str) -> FormGenerator:
    # TODO add additional fields to form if needed

    class CreateExample1Form(FormPage):
        model_config = ConfigDict(title=product_name)

        customer_id: CustomerId

        example1_settings: Label
        divider_1: Divider

        example_str_enum_1: validated_example_str_enum_1
        unmodifiable_str: str
        modifiable_boolean: bool
        annotated_int: validated_annotated_int | None = None
        always_optional_str: str | None = None

    user_input = yield CreateExample1Form
    user_input_dict = user_input.dict()

    summary_fields = [
        "example_str_enum_1",
        "unmodifiable_str",
        "modifiable_boolean",
        "annotated_int",
        "always_optional_str",
    ]
    yield from create_summary_form(user_input_dict, product_name, summary_fields)

    return user_input_dict


@step("Construct Subscription model")
def construct_example1_model(
    product: UUIDstr,
    customer_id: UUIDstr,
    example_str_enum_1: ExampleStrEnum1,
    unmodifiable_str: str,
    modifiable_boolean: bool,
    annotated_int: AnnotatedInt | None,
    always_optional_str: str | None,
) -> State:
    example1 = Example1Inactive.from_product_id(
        product_id=product,
        customer_id=customer_id,
        status=SubscriptionLifecycle.INITIAL,
    )
    example1.example1.example_str_enum_1 = example_str_enum_1
    example1.example1.unmodifiable_str = unmodifiable_str
    example1.example1.modifiable_boolean = modifiable_boolean
    example1.example1.annotated_int = annotated_int
    example1.example1.always_optional_str = always_optional_str

    example1 = Example1Provisioning.from_other_lifecycle(example1, SubscriptionLifecycle.PROVISIONING)
    example1.description = subscription_description(example1)

    return {
        "subscription": example1,
        "subscription_id": example1.subscription_id,  # necessary to be able to use older generic step functions
        "subscription_description": example1.description,
    }


additional_steps = begin


@create_workflow("Create example1", initial_input_form=initial_input_form_generator, additional_steps=additional_steps)
def create_example1() -> StepList:
    return (
        begin >> construct_example1_model >> store_process_subscription(Target.CREATE)
        # TODO add provision step(s)
    )
