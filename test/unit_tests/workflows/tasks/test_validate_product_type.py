import pytest

from orchestrator.db import SubscriptionTable, db
from orchestrator.targets import Target
from test.unit_tests.workflows import (
    assert_complete,
    extract_state,
    run_workflow,
)


@pytest.mark.workflow
def test_check_subscriptions(generic_subscription_1, validation_workflow_instance):
    product = db.session.get(SubscriptionTable, generic_subscription_1).product
    product.workflows.append(validation_workflow_instance)
    db.session.add(product)
    db.session.commit()

    init_data = {
        "product_type": "Generic",
    }

    result, process, step_log = run_workflow("task_validate_product_type", init_data)

    assert_complete(result)

    state = extract_state(result)

    assert state["product_type"] == "Generic"
    assert state["workflow_name"] == "task_validate_product_type"
    assert state["workflow_target"] == Target.SYSTEM

    result = state["result"]

    assert len(result) == 1
    assert result[0]["total_workflows_validated"] == 1
    assert len(result[0]["workflows"]) == 1
    assert result[0]["workflows"][0]["workflow_name"] == "validation_workflow"
    assert result[0]["workflows"][0]["product_type"] == "Generic"
