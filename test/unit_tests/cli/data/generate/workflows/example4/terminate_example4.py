import structlog
from orchestrator.forms import FormPage
from orchestrator.forms.validators import DisplaySubscription
from orchestrator.types import InputForm, State, UUIDstr
from orchestrator.workflow import StepList, begin, step
from orchestrator.workflows.utils import terminate_workflow

from products.product_types.example4 import Example4

logger = structlog.get_logger(__name__)


def terminate_initial_input_form_generator(subscription_id: UUIDstr, customer_id: UUIDstr) -> InputForm:
    temp_subscription_id = subscription_id

    class TerminateExample4Form(FormPage):
        subscription_id: DisplaySubscription = temp_subscription_id  # type: ignore

    return TerminateExample4Form


@step("Delete subscription from OSS/BSS")
def delete_subscription_from_oss_bss(subscription: Example4) -> State:
    # TODO: add actual call to OSS/BSS to delete subscription

    return {}


additional_steps = begin


@terminate_workflow(
    "Terminate example4", initial_input_form=terminate_initial_input_form_generator, additional_steps=additional_steps
)
def terminate_example4() -> StepList:
    return (
        begin >> delete_subscription_from_oss_bss
        # TODO: fill in additional steps if needed
    )
