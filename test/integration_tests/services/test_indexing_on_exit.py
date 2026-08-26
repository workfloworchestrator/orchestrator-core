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

"""Integration tests asserting that processes and subscriptions are indexed when a process exits."""

from datetime import timedelta
from unittest.mock import call, patch
from uuid import UUID

import pytest

from nwastdlib import const
from orchestrator.core.config.assignee import Assignee
from orchestrator.core.db import ProcessTable, db
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.services.processes import abort_process, fail_awaiting_process, start_process
from orchestrator.core.targets import Target
from orchestrator.core.utils.datetime import nowtz
from orchestrator.core.workflow import ProcessStatus, callback_step, done, init, inputstep, step, workflow
from pydantic_forms.core import FormPage
from pydantic_forms.types import UUIDstr
from test.integration_tests.workflows import WorkflowInstanceForTests, assert_aborted

pytestmark = pytest.mark.search


@step("Succeeding step")
def succeeding_step():
    return {"result": "ok"}


@step("Failing step")
def failing_step():
    raise ValueError("step blew up")


@step("Store subscription id")
def store_subscription_id_step(subscription_id):
    return {"subscription_id": subscription_id}


@inputstep("Wait for user input", assignee=Assignee.SYSTEM)
def suspending_step():
    class ConfirmForm(FormPage):
        confirm: bool = True

    user_input = yield ConfirmForm
    return user_input.model_dump()


class SubscriptionForm(FormPage):
    subscription_id: UUIDstr


# No description argument: passing one triggers the deprecation warning in workflow.py:600.
@workflow(target=Target.SYSTEM)
def indexing_success_wf():
    return init >> succeeding_step >> done


@workflow(target=Target.SYSTEM)
def indexing_failure_wf():
    return init >> failing_step >> done


# Suspends on the inputstep, so `start_process` returns with the process still SUSPENDED. That is a
# prerequisite for the abort test: `abort_wf` early-returns unchanged on an already-complete state.
@workflow(target=Target.SYSTEM)
def indexing_abort_wf():
    return init >> succeeding_step >> suspending_step >> done


@workflow(target=Target.SYSTEM, initial_input_form=const(SubscriptionForm))
def indexing_subscription_wf():
    return init >> store_subscription_id_step >> done


@step("Call external system")
def calling_step():
    return {}


@step("Validate callback result")
def validating_step():
    return {}


# Awaits a callback that never arrives, so the process parks in AWAITING_CALLBACK until the
# timeout sweep fails it. Keeps `subscription_id` in state, which `fail_awaiting_wf` preserves.
@workflow(target=Target.SYSTEM, initial_input_form=const(SubscriptionForm))
def indexing_timeout_wf():
    return (
        init
        >> store_subscription_id_step
        >> callback_step(
            name="Await external system",
            action_step=calling_step,
            validate_step=validating_step,
            timeout=300,
        )
        >> done
    )


def _backdate_await_step(process_id: UUIDstr, seconds: int) -> None:
    """Move the awaiting step's started_at into the past so its timeout counts as elapsed."""
    process = db.session.get(ProcessTable, process_id)
    assert process is not None
    await_step = process.steps[-1]
    await_step.started_at = nowtz() - timedelta(seconds=seconds)
    db.session.add(await_step)
    db.session.commit()


# Every database assertion stays inside the `WorkflowInstanceForTests` block: leaving it deletes the
# WorkflowTable row, which cascades (`WorkflowTable.processes`, delete-orphan) to the process under test.


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_completed_process_is_indexed_with_final_status(mock_run_indexing):
    # Capture the status as the DB saw it at the moment indexing ran. Asserting the status only
    # after the workflow returns would pass even if indexing had run before the commit.
    status_when_indexed = []

    def record_status_at_call_time(entity_type, entity_id):
        indexed = db.session.get(ProcessTable, UUID(entity_id))
        status_when_indexed.append(indexed.last_status if indexed else None)

    mock_run_indexing.side_effect = record_status_at_call_time

    with WorkflowInstanceForTests(indexing_success_wf, "indexing_success_wf"):
        process_id = start_process("indexing_success_wf", [{}])

        process = db.session.get(ProcessTable, process_id)
        assert process.last_status == ProcessStatus.COMPLETED

        # Indexing happened once, after the terminal status was committed. No subscription in
        # state, so the process is the only entity indexed.
        assert call(EntityType.PROCESS, str(process_id)) in mock_run_indexing.call_args_list
        assert mock_run_indexing.call_count == 1

        # The ordering guarantee: COMPLETED was already committed when the indexer was invoked.
        assert status_when_indexed == [ProcessStatus.COMPLETED]


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_failed_process_is_indexed(mock_run_indexing):
    with WorkflowInstanceForTests(indexing_failure_wf, "indexing_failure_wf"):
        process_id = start_process("indexing_failure_wf", [{}])

        process = db.session.get(ProcessTable, process_id)
        assert process.last_status == ProcessStatus.FAILED

        assert call(EntityType.PROCESS, str(process_id)) in mock_run_indexing.call_args_list


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_aborted_process_is_indexed(mock_run_indexing):
    with WorkflowInstanceForTests(indexing_abort_wf, "indexing_abort_wf"):
        process_id = start_process("indexing_abort_wf", [{}])

        # The process must really be suspended: `abort_wf` returns the state untouched when it is
        # already complete, which would make the abort below a no-op and this test vacuous.
        process = db.session.get(ProcessTable, process_id)
        assert process.last_status == ProcessStatus.SUSPENDED

        mock_run_indexing.reset_mock()

        result = abort_process(process, user="tester")

        assert_aborted(result)
        db.session.refresh(process)
        assert process.last_status == ProcessStatus.ABORTED

        assert call(EntityType.PROCESS, str(process_id)) in mock_run_indexing.call_args_list


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_timed_out_awaiting_process_is_indexed(mock_run_indexing, generic_subscription_1):
    """The callback-timeout exit is the one Failed path whose state keeps its subscription.

    `fail_awaiting_wf` rebuilds the state from the previous one, unlike a failing step which
    replaces it with an error record. It is also the only exit called from inside another
    workflow's step, so it runs against a live caller session.
    """
    with WorkflowInstanceForTests(indexing_timeout_wf, "indexing_timeout_wf"):
        process_id = start_process("indexing_timeout_wf", [{"subscription_id": generic_subscription_1}])

        process = db.session.get(ProcessTable, process_id)
        assert process.last_status == ProcessStatus.AWAITING_CALLBACK

        _backdate_await_step(process_id, seconds=600)
        mock_run_indexing.reset_mock()

        fail_awaiting_process(db.session.get(ProcessTable, process_id))

        db.session.refresh(process)
        assert process.last_status == ProcessStatus.FAILED

        assert call(EntityType.PROCESS, str(process_id)) in mock_run_indexing.call_args_list
        assert call(EntityType.SUBSCRIPTION, str(generic_subscription_1)) in mock_run_indexing.call_args_list


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_subscription_in_state_is_indexed(mock_run_indexing, generic_subscription_1):
    with WorkflowInstanceForTests(indexing_subscription_wf, "indexing_subscription_wf"):
        process_id = start_process("indexing_subscription_wf", [{"subscription_id": generic_subscription_1}])

        assert call(EntityType.SUBSCRIPTION, str(generic_subscription_1)) in mock_run_indexing.call_args_list
        assert call(EntityType.PROCESS, str(process_id)) in mock_run_indexing.call_args_list
