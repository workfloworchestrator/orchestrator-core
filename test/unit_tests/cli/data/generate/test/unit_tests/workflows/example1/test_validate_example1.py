import pytest

from test.unit_tests.workflows import assert_complete, extract_state, run_workflow


@pytest.mark.workflow()
def test_happy_flow(responses, example1_subscription):
    # when

    result, _, _ = run_workflow("validate_example1", {"subscription_id": example1_subscription})

    # then

    assert_complete(result)
    state = extract_state(result)
    assert state["check_core_db"] is True


@pytest.mark.workflow()
def test_validate_example_in_some_oss(responses, example1_subscription):
    # given

    # TODO: set test conditions or fixture so that "Validate that the example1 subscription is correctly administered in some external system" triggers

    # when

    with pytest.raises(AssertionError) as error:
        result, _, _ = run_workflow("validate_example1", [{"subscription_id": example1_subscription}, {}])

    # then

    assert (
        error.value.errors[0]["msg"]
        == "Validate that the example1 subscription is correctly administered in some external system"
    )
