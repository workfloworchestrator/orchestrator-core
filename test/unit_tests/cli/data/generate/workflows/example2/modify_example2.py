import structlog
from orchestrator.domain import SubscriptionModel
from orchestrator.forms import FormPage
from orchestrator.forms.validators import CustomerId, Divider
from orchestrator.types import FormGenerator, State, SubscriptionLifecycle, UUIDstr
from orchestrator.workflow import StepList, begin, step
from orchestrator.workflows.steps import set_status
from orchestrator.workflows.utils import modify_workflow

from products.product_blocks.example2 import ExampleIntEnum2
from products.product_types.example2 import Example2, Example2Provisioning


def subscription_description(subscription: SubscriptionModel) -> str:
    """The suggested pattern is to implement a subscription service that generates a subscription specific
    description, in case that is not present the description will just be set to the product name.
    """
    return f"{subscription.product.name} subscription"


logger = structlog.get_logger(__name__)


def initial_input_form_generator(subscription_id: UUIDstr) -> FormGenerator:
    subscription = Example2.from_subscription(subscription_id)
    example2 = subscription.example2

    # TODO fill in additional fields if needed

    class ModifyExample2Form(FormPage):
        customer_id: CustomerId = subscription.customer_id  # type: ignore

        divider_1: Divider

        example_int_enum_2: ExampleIntEnum2 | None = example2.example_int_enum_2

    user_input = yield ModifyExample2Form
    user_input_dict = user_input.dict()

    return user_input_dict | {"subscription": subscription}


@step("Update subscription")
def update_subscription(
    subscription: Example2Provisioning,
    example_int_enum_2: ExampleIntEnum2 | None,
) -> State:
    # TODO: get all modified fields
    subscription.example2.example_int_enum_2 = example_int_enum_2

    return {"subscription": subscription}


@step("Update subscription description")
def update_subscription_description(subscription: Example2) -> State:
    subscription.description = subscription_description(subscription)
    return {"subscription": subscription}


additional_steps = begin


@modify_workflow("Modify example2", initial_input_form=initial_input_form_generator, additional_steps=additional_steps)
def modify_example2() -> StepList:
    return (
        begin
        >> set_status(SubscriptionLifecycle.PROVISIONING)
        >> update_subscription
        >> update_subscription_description
        # TODO add additional steps if needed
        >> set_status(SubscriptionLifecycle.ACTIVE)
    )
