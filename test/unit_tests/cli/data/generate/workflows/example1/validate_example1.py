import structlog
from orchestrator.types import State
from orchestrator.workflow import StepList, begin, step
from orchestrator.workflows.utils import validate_workflow

from products.product_types.example1 import Example1

logger = structlog.get_logger(__name__)


@step("Load initial state")
def load_initial_state_example1(subscription: Example1) -> State:
    return {
        "subscription": subscription,
    }


@step("Validate that the example1 subscription is correctly administered in some external system")
def check_validate_example_in_some_oss(subscription: Example1) -> State:
    # TODO: add validation for "Validate that the example1 subscription is correctly administered in some external system"
    if True:
        raise ValueError("Validate that the example1 subscription is correctly administered in some external system")

    return {}


@validate_workflow("Validate example1")
def validate_example1() -> StepList:
    return begin >> load_initial_state_example1 >> check_validate_example_in_some_oss
