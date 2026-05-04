# Copyright 2019-2026 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
from sqlalchemy import text

from orchestrator.core.db import db
from orchestrator.core.services.subscriptions import get_subscription
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
