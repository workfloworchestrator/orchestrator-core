import pytest

from test.unit_tests.workflows import assert_complete, extract_state, run_workflow


@pytest.mark.workflow()
def test_happy_flow(responses, example4_subscription):
    # when

    result, _, _ = run_workflow("validate_example4", {"subscription_id": example4_subscription})

    # then

    assert_complete(result)
    state = extract_state(result)
    assert state["check_core_db"] is True
