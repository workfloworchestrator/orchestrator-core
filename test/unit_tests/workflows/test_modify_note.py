import pytest

from orchestrator.services.subscriptions import get_subscription
from test.unit_tests.workflows import assert_complete, extract_state, run_workflow

TEST = "Some note"


@pytest.mark.workflow
def test_modify_note(responses, generic_subscription_1):
    init_state = [{"subscription_id": generic_subscription_1}, {"note": TEST}]

    result, process, step_log = run_workflow("modify_note", init_state)
    assert_complete(result)

    # assert state for correctness
    state = extract_state(result)
    assert state["old_note"] is None
    assert state["note"] == TEST
    assert state["__old_subscriptions__"].get(generic_subscription_1)
    assert state["__old_subscriptions__"][generic_subscription_1]["note"] is None
    assert state["__old_subscriptions__"][generic_subscription_1]["description"] == "Generic Subscription One"

    # assert subscription for correctness
    subscription = get_subscription(generic_subscription_1)
    assert subscription.note == TEST
