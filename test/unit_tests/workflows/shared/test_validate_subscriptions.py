import pytest

from orchestrator.db import SubscriptionTable, WorkflowTable, db
from orchestrator.forms import FormValidationError
from orchestrator.targets import Target
from orchestrator.workflow import StepList, begin, step
from orchestrator.workflows.utils import validate_workflow
from test.unit_tests.workflows import (
    WorkflowInstanceForTests,
    assert_complete,
    assert_failed,
    extract_error,
    run_workflow,
)


@validate_workflow("Test Validation")
def validation_workflow() -> StepList:
    return StepList([])


def test_happy_flow(generic_subscription_1, validation_workflow_instance):
    product = SubscriptionTable.query.get(generic_subscription_1).product
    product.workflows.append(WorkflowTable(name="validation_workflow", target=Target.SYSTEM))
    db.session.add(product)
    db.session.commit()

    result, process, step_log = run_workflow("validation_workflow", {"subscription_id": generic_subscription_1})
    assert_complete(result)


def test_no_subscription(validation_workflow_instance):
    with pytest.raises(FormValidationError) as error_info:
        run_workflow("validation_workflow", {"subscription_id": None})
    assert "none is not an allowed value" in str(error_info.value)


def test_failed_validation(generic_subscription_1: str, validation_workflow_instance) -> None:
    @step("Fail")
    def fail():
        raise ValueError("Failed")

    @validate_workflow("Failing Validation")
    def failing_validation_workflow() -> StepList:
        return begin >> fail

    with WorkflowInstanceForTests(failing_validation_workflow, "failing_validation_workflow"):
        product = SubscriptionTable.query.get(generic_subscription_1).product
        product.workflows.append(WorkflowTable(name="failing_validation_workflow", target=Target.SYSTEM))
        db.session.add(product)
        db.session.commit()

        result, process, step_log = run_workflow(
            "failing_validation_workflow", {"subscription_id": generic_subscription_1}
        )
        assert_failed(result)
        assert "Failed" in extract_error(result)
