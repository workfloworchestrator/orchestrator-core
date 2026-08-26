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

from unittest.mock import call, patch

from nwastdlib import const
from orchestrator.core.db import ProcessTable, db
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.services.processes import abort_process, start_process
from orchestrator.core.targets import Target
from orchestrator.core.workflow import ProcessStatus, done, init, step, workflow
from pydantic_forms.core import FormPage
from pydantic_forms.types import UUIDstr
from test.integration_tests.workflows import WorkflowInstanceForTests


@step("Succeeding step")
def succeeding_step():
    return {"result": "ok"}


@step("Failing step")
def failing_step():
    raise ValueError("step blew up")


@step("Store subscription id")
def store_subscription_id_step(subscription_id):
    return {"subscription_id": subscription_id}


class SubscriptionForm(FormPage):
    subscription_id: UUIDstr


# No description argument: passing one triggers the deprecation warning in workflow.py:600.
@workflow(target=Target.SYSTEM)
def indexing_success_wf():
    return init >> succeeding_step >> done


@workflow(target=Target.SYSTEM)
def indexing_failure_wf():
    return init >> failing_step >> done


@workflow(target=Target.SYSTEM, initial_input_form=const(SubscriptionForm))
def indexing_subscription_wf():
    return init >> store_subscription_id_step >> done


# Every database assertion stays inside the `WorkflowInstanceForTests` block: leaving it deletes the
# WorkflowTable row, which cascades (`WorkflowTable.processes`, delete-orphan) to the process under test.


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_completed_process_is_indexed_with_final_status(mock_run_indexing):
    with WorkflowInstanceForTests(indexing_success_wf, "indexing_success_wf"):
        process_id = start_process("indexing_success_wf", [{}])

        process = db.session.get(ProcessTable, process_id)
        assert process.last_status == ProcessStatus.COMPLETED

        # Indexing happened once, after the terminal status was committed. No subscription in
        # state, so the process is the only entity indexed.
        assert call(EntityType.PROCESS, str(process_id)) in mock_run_indexing.call_args_list
        assert mock_run_indexing.call_count == 1


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_failed_process_is_indexed(mock_run_indexing):
    with WorkflowInstanceForTests(indexing_failure_wf, "indexing_failure_wf"):
        process_id = start_process("indexing_failure_wf", [{}])

        process = db.session.get(ProcessTable, process_id)
        assert process.last_status == ProcessStatus.FAILED

        assert call(EntityType.PROCESS, str(process_id)) in mock_run_indexing.call_args_list


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_aborted_process_is_indexed(mock_run_indexing):
    with WorkflowInstanceForTests(indexing_success_wf, "indexing_abort_wf"):
        process_id = start_process("indexing_abort_wf", [{}])
        process = db.session.get(ProcessTable, process_id)
        mock_run_indexing.reset_mock()

        abort_process(process, user="tester")

    assert call(EntityType.PROCESS, str(process_id)) in mock_run_indexing.call_args_list


@patch("orchestrator.core.search.indexing.hooks.run_indexing_for_entity")
def test_subscription_in_state_is_indexed(mock_run_indexing, generic_subscription_1):
    with WorkflowInstanceForTests(indexing_subscription_wf, "indexing_subscription_wf"):
        process_id = start_process("indexing_subscription_wf", [{"subscription_id": generic_subscription_1}])

        assert call(EntityType.SUBSCRIPTION, str(generic_subscription_1)) in mock_run_indexing.call_args_list
        assert call(EntityType.PROCESS, str(process_id)) in mock_run_indexing.call_args_list
