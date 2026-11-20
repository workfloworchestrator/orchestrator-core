import structlog
from orchestrator.core.forms import FormPage
from orchestrator.core.forms.validators import CustomerId, Divider
from orchestrator.core.types import SubscriptionLifecycle
from orchestrator.core.workflow import StepList, begin, step
from orchestrator.core.workflows.steps import set_status
from orchestrator.core.workflows.utils import modify_workflow
from pydantic_forms.types import FormGenerator, State, UUIDstr

from products.product_blocks.example2 import ExampleIntEnum2
from products.product_types.example2 import Example2, Example2Provisioning
from products.services.description import description

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
    user_input_dict = user_input.model_dump()

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
    subscription.description = description(subscription)
    return {"subscription": subscription}


additional_steps = begin


@modify_workflow(initial_input_form=initial_input_form_generator, additional_steps=additional_steps)
def modify_example2() -> StepList:
    return (
        begin
        >> set_status(SubscriptionLifecycle.PROVISIONING)
        >> update_subscription
        >> update_subscription_description
        # TODO add additional steps if needed
        >> set_status(SubscriptionLifecycle.ACTIVE)
    )
