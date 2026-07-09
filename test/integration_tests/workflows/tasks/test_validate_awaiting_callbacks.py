# Copyright 2026 SURF.
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

from datetime import timedelta
from unittest import mock
from uuid import uuid4

import pytest

from orchestrator.core.config.assignee import Assignee
from orchestrator.core.db import ProcessStepTable, ProcessTable, WorkflowTable, db
from orchestrator.core.targets import Target
from orchestrator.core.utils.datetime import nowtz
from orchestrator.core.workflow import CALLBACK_TIMEOUT_KEY, ProcessStatus
from test.integration_tests.workflows import assert_complete, extract_state, run_workflow


@pytest.fixture
def awaiting_workflow():
    wf = WorkflowTable(workflow_id=uuid4(), name="Awaiting workflow", target=Target.CREATE, description="Description")
    db.session.add(wf)
    db.session.commit()
    return wf


def _make_awaiting_process(awaiting_workflow, *, timeout: int | None, started_seconds_ago: int) -> ProcessTable:
    pid = uuid4()
    process = ProcessTable(
        process_id=pid,
        workflow_id=awaiting_workflow.workflow_id,
        last_status=ProcessStatus.AWAITING_CALLBACK,
        assignee=Assignee.SYSTEM,
        last_step="Await callback",
        created_by="tester",
    )
    state = {"__sub_step": "Await callback"} | ({CALLBACK_TIMEOUT_KEY: timeout} if timeout is not None else {})
    await_step = ProcessStepTable(
        process_id=pid,
        name="Await callback",
        status=ProcessStatus.AWAITING_CALLBACK,
        state=state,
        created_by="tester",
        started_at=nowtz() - timedelta(seconds=started_seconds_ago),
    )
    db.session.add_all([process, await_step])
    db.session.commit()
    return process


def test_task_fails_only_timed_out_callbacks(awaiting_workflow):
    expired = _make_awaiting_process(awaiting_workflow, timeout=300, started_seconds_ago=600)
    not_expired = _make_awaiting_process(awaiting_workflow, timeout=300, started_seconds_ago=60)
    no_timeout = _make_awaiting_process(awaiting_workflow, timeout=None, started_seconds_ago=600)

    result, _, _ = run_workflow("task_validate_awaiting_callbacks", {})
    assert_complete(result)

    res = extract_state(result)
    assert res["number_of_timed_out_processes"] == 1
    assert res["failed_process_ids"] == [str(expired.process_id)]

    assert db.session.get(ProcessTable, expired.process_id).last_status == ProcessStatus.FAILED
    assert db.session.get(ProcessTable, not_expired.process_id).last_status == ProcessStatus.AWAITING_CALLBACK
    assert db.session.get(ProcessTable, no_timeout.process_id).last_status == ProcessStatus.AWAITING_CALLBACK


@mock.patch("orchestrator.core.workflows.tasks.validate_awaiting_callbacks.processes.fail_awaiting_process")
def test_task_skips_process_when_failing_raises(mock_fail, awaiting_workflow):
    # Exercises the per-process error handling: a failure to fail one process is logged and skipped.
    mock_fail.side_effect = Exception("boom")
    _make_awaiting_process(awaiting_workflow, timeout=300, started_seconds_ago=600)

    result, _, _ = run_workflow("task_validate_awaiting_callbacks", {})
    assert_complete(result)

    res = extract_state(result)
    assert res["number_of_timed_out_processes"] == 1
    assert res["failed_process_ids"] == []
