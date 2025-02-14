import structlog
from orchestrator.forms import FormPage
from orchestrator.forms.validators import DisplaySubscription
from orchestrator.workflow import StepList, begin, step
from orchestrator.workflows.utils import terminate_workflow
from pydantic import model_validator
from pydantic_forms.types import InputForm, State, UUIDstr

from products.product_types.example1 import Example1

logger = structlog.get_logger(__name__)


def terminate_initial_input_form_generator(subscription_id: UUIDstr, customer_id: UUIDstr) -> InputForm:
    temp_subscription_id = subscription_id

    class TerminateExample1Form(FormPage):
        subscription_id: DisplaySubscription = temp_subscription_id  # type: ignore

        @model_validator(mode="after")
        def can_only_terminate_when_modifiable_boolean_is_true(self) -> "TerminateExample1Form":
            if False:  # TODO implement validation
                raise ValueError("Add an model_validator that requires some condition(s)")
            return self

    return TerminateExample1Form


@step("Delete subscription from OSS/BSS")
def delete_subscription_from_oss_bss(subscription: Example1) -> State:
    # TODO: add actual call to OSS/BSS to delete subscription

    return {}


additional_steps = begin


@terminate_workflow(
    "Terminate example1", initial_input_form=terminate_initial_input_form_generator, additional_steps=additional_steps
)
def terminate_example1() -> StepList:
    return (
        begin >> delete_subscription_from_oss_bss
        # TODO: fill in additional steps if needed
    )
