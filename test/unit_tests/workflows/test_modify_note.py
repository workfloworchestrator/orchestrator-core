import pytest
from sqlalchemy import text

from orchestrator.db import db
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


@pytest.mark.workflow
def test_modify_note_empty_string_stored_as_null(responses, generic_subscription_1):
    """Test that empty string note values are stored as NULL in the database."""

    # Now set it to empty string - should be stored as NULL
    init_state = [{"subscription_id": generic_subscription_1}, {"note": ""}]
    result, process, step_log = run_workflow("modify_note", init_state)
    assert_complete(result)

    # Verify via ORM that note is None
    subscription = get_subscription(generic_subscription_1)
    assert subscription.note is None

    # Verify directly in database that the value is actually NULL (not empty string)
    result = db.session.execute(
        text("SELECT note FROM subscriptions WHERE subscription_id = :sub_id"),
        {"sub_id": generic_subscription_1},
    )
    row = result.fetchone()
    assert row[0] is None, f"Expected NULL in database, but got: {row[0]!r}"
