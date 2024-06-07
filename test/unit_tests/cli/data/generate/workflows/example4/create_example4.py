import structlog
from orchestrator.domain import SubscriptionModel
from orchestrator.forms import FormPage
from orchestrator.forms.validators import CustomerId, Divider, Label
from orchestrator.targets import Target
from orchestrator.types import FormGenerator, State, SubscriptionLifecycle, UUIDstr
from orchestrator.workflow import StepList, begin, step
from orchestrator.workflows.steps import store_process_subscription
from orchestrator.workflows.utils import create_workflow
from pydantic import ConfigDict

from products.product_types.example4 import Example4Inactive, Example4Provisioning


def subscription_description(subscription: SubscriptionModel) -> str:
    """Generate subscription description.

    The suggested pattern is to implement a subscription service that generates a subscription specific
    description, in case that is not present the description will just be set to the product name.
    """
    return f"{subscription.product.name} subscription"


logger = structlog.get_logger(__name__)


def initial_input_form_generator(product_name: str) -> FormGenerator:
    # TODO add additional fields to form if needed

    class CreateExample4Form(FormPage):
        model_config = ConfigDict(title=product_name)

        customer_id: CustomerId

        example4_settings: Label
        divider_1: Divider

        num_val: int | None = None

    user_input = yield CreateExample4Form
    user_input_dict = user_input.dict()

    return user_input_dict


@step("Construct Subscription model")
def construct_example4_model(
    product: UUIDstr,
    customer_id: UUIDstr,
    num_val: int | None,
) -> State:
    example4 = Example4Inactive.from_product_id(
        product_id=product,
        customer_id=customer_id,
        status=SubscriptionLifecycle.INITIAL,
    )
    example4.example4.num_val = num_val

    example4 = Example4Provisioning.from_other_lifecycle(example4, SubscriptionLifecycle.PROVISIONING)
    example4.description = subscription_description(example4)

    return {
        "subscription": example4,
        "subscription_id": example4.subscription_id,  # necessary to be able to use older generic step functions
        "subscription_description": example4.description,
    }


additional_steps = begin


@create_workflow("Create example4", initial_input_form=initial_input_form_generator, additional_steps=additional_steps)
def create_example4() -> StepList:
    return (
        begin >> construct_example4_model >> store_process_subscription(Target.CREATE)
        # TODO add provision step(s)
    )
