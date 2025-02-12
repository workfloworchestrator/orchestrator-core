import structlog
from orchestrator.domain import SubscriptionModel
from orchestrator.forms import FormPage
from orchestrator.forms.validators import CustomerId, Divider, Label
from orchestrator.targets import Target
from orchestrator.types import SubscriptionLifecycle
from orchestrator.workflow import StepList, begin, step
from orchestrator.workflows.steps import store_process_subscription
from orchestrator.workflows.utils import create_workflow
from pydantic import ConfigDict
from pydantic_forms.types import FormGenerator, State, UUIDstr

from products.product_blocks.example2 import ExampleIntEnum2
from products.product_types.example2 import Example2Inactive, Example2Provisioning


def subscription_description(subscription: SubscriptionModel) -> str:
    """Generate subscription description.

    The suggested pattern is to implement a subscription service that generates a subscription specific
    description, in case that is not present the description will just be set to the product name.
    """
    return f"{subscription.product.name} subscription"


logger = structlog.get_logger(__name__)


def initial_input_form_generator(product_name: str) -> FormGenerator:
    # TODO add additional fields to form if needed

    class CreateExample2Form(FormPage):
        model_config = ConfigDict(title=product_name)

        customer_id: CustomerId

        example2_settings: Label
        divider_1: Divider

        example_int_enum_2: ExampleIntEnum2 | None = None

    user_input = yield CreateExample2Form
    user_input_dict = user_input.dict()

    return user_input_dict


@step("Construct Subscription model")
def construct_example2_model(
    product: UUIDstr,
    customer_id: UUIDstr,
    example_int_enum_2: ExampleIntEnum2 | None,
) -> State:
    example2 = Example2Inactive.from_product_id(
        product_id=product,
        customer_id=customer_id,
        status=SubscriptionLifecycle.INITIAL,
    )
    example2.example2.example_int_enum_2 = example_int_enum_2

    example2 = Example2Provisioning.from_other_lifecycle(example2, SubscriptionLifecycle.PROVISIONING)
    example2.description = subscription_description(example2)

    return {
        "subscription": example2,
        "subscription_id": example2.subscription_id,  # necessary to be able to use older generic step functions
        "subscription_description": example2.description,
    }


additional_steps = begin


@create_workflow("Create example2", initial_input_form=initial_input_form_generator, additional_steps=additional_steps)
def create_example2() -> StepList:
    return (
        begin >> construct_example2_model >> store_process_subscription(Target.CREATE)
        # TODO add provision step(s)
    )
