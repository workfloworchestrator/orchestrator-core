# Copyright 2019-2026 SURF, GÉANT, ESnet.
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

"""Integration test: a failing middle step is durably logged.

Asserts the framework's per-step session lifecycle persists step rows even when
a middle step raises. The expected `process_steps` table after running a
3-step workflow whose second step raises must contain:

* a "success" row for step 1
* a "failed" row for step 2 (the raising step)
* NO row for step 3 (execution stops on failure)
"""

from __future__ import annotations

from unittest import mock

import pytest
from sqlalchemy import select

from orchestrator.db import ProcessStepTable, db
from orchestrator.services.processes import _get_process, start_process
from orchestrator.workflow import StepStatus, done, init, step, workflow
from pydantic_forms.core import FormPage
from test.unit_tests.workflows import WorkflowInstanceForTests


def _initial_input_form():
    class TestForm(FormPage):
        test_field: str

    user_input = yield TestForm
    return user_input.model_dump()


@step("Step 1 success")
def _step_1_success(test_field: str) -> dict:
    return {"step_1_done": True, "test_field": test_field}


@step("Step 2 boom")
def _step_2_boom() -> dict:
    raise RuntimeError("kaboom")


@step("Step 3 never runs")
def _step_3_never_runs() -> dict:
    return {"step_3_done": True}


def _run_sync(process_id, fn):
    fn()
    return process_id


@pytest.mark.workflow
@mock.patch("orchestrator.services.processes._run_process_async")
def test_failed_middle_step_is_logged(mock_run_process_async, db_session):  # noqa: ARG001
    """A 3-step workflow with a failing middle step persists rows for steps 1 and 2 only."""
    mock_run_process_async.side_effect = _run_sync

    @workflow(initial_input_form=_initial_input_form)
    def _three_step_workflow():
        return init >> _step_1_success >> _step_2_boom >> _step_3_never_runs >> done

    with mock.patch.object(db.session, "rollback"):
        with WorkflowInstanceForTests(_three_step_workflow, "three_step_workflow"):
            process_id = start_process("three_step_workflow", user_inputs=[{"test_field": "hello"}])

            process = _get_process(process_id)
            assert process is not None

            step_rows = db.session.scalars(
                select(ProcessStepTable)
                .where(ProcessStepTable.process_id == process_id)
                .order_by(ProcessStepTable.completed_at)
            ).all()

            # Always present: framework writes a "Start" row before user steps; we
            # care about the post-Start steps below.
            recorded = [(row.name, row.status) for row in step_rows]

            # Step 1 should have succeeded and been persisted.
            assert ("Step 1 success", StepStatus.SUCCESS) in recorded, recorded

            # Step 2 should have failed and been persisted.
            assert ("Step 2 boom", StepStatus.FAILED) in recorded, recorded

            # Step 3 must NOT appear: execution stops at the failed step.
            assert all(name != "Step 3 never runs" for name, _ in recorded), recorded
