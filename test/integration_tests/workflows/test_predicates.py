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

"""Tests for no_uncompleted_instance predicate: pass on zero count, fail with message on nonzero."""

from typing import cast
from uuid import uuid4

import pytest

from orchestrator.core.db import ProcessStepTable, ProcessTable, db
from orchestrator.core.workflow import (
    CALLBACK_TIMEOUT_KEY,
    PredicateContext,
    ProcessStatus,
    RunPredicateFail,
    RunPredicatePass,
    StepStatus,
    Workflow,
)
from orchestrator.core.workflows.predicates import awaiting_callbacks_exist, no_uncompleted_instance


def _context(workflow_key: str) -> PredicateContext:
    # The predicates only read workflow_key; workflow is irrelevant here.
    return PredicateContext(workflow=cast(Workflow, None), workflow_key=workflow_key)


@pytest.fixture
def test_process(test_workflow, generic_subscription_1):
    process = ProcessTable(process_id=uuid4(), workflow_id=test_workflow.workflow_id, last_status=ProcessStatus.CREATED)
    db.session.add(process)
    db.session.commit()
    return process


@pytest.mark.parametrize(
    "process_status,expected_type",
    [
        pytest.param(ProcessStatus.COMPLETED, RunPredicatePass, id="completed"),
        pytest.param(ProcessStatus.ABORTED, RunPredicatePass, id="aborted"),
        pytest.param(ProcessStatus.CREATED, RunPredicateFail, id="created"),
        pytest.param(ProcessStatus.RUNNING, RunPredicateFail, id="running"),
        pytest.param(ProcessStatus.FAILED, RunPredicateFail, id="failed"),
    ],
)
def test_no_uncompleted_by_process_last_status(test_process, test_workflow, process_status, expected_type) -> None:
    test_process.last_status = process_status
    db.session.add(test_process)
    db.session.commit()

    context = _context(test_workflow.name)

    result = no_uncompleted_instance(context)

    assert isinstance(result, expected_type)


def _awaiting_process(test_workflow, *, with_timeout: bool) -> ProcessTable:
    process = ProcessTable(
        process_id=uuid4(), workflow_id=test_workflow.workflow_id, last_status=ProcessStatus.AWAITING_CALLBACK
    )
    db.session.add(process)
    db.session.add(
        ProcessStepTable(
            process_id=process.process_id,
            name="Await callback",
            status=StepStatus.AWAITING_CALLBACK,
            state={CALLBACK_TIMEOUT_KEY: 300} if with_timeout else {},
        )
    )
    db.session.commit()
    return process


def test_awaiting_callbacks_exist_pass(test_workflow, generic_subscription_1) -> None:
    _awaiting_process(test_workflow, with_timeout=True)

    # workflow_key with no uncompleted instances of itself, so only the awaiting-existence check matters
    context = _context("task_validate_awaiting_callbacks")

    assert isinstance(awaiting_callbacks_exist(context), RunPredicatePass)


@pytest.mark.parametrize(
    "create_awaiting_without_timeout",
    [
        pytest.param(False, id="no-awaiting-processes"),
        pytest.param(True, id="awaiting-without-timeout"),
    ],
)
def test_awaiting_callbacks_exist_fail(test_workflow, generic_subscription_1, create_awaiting_without_timeout) -> None:
    if create_awaiting_without_timeout:
        _awaiting_process(test_workflow, with_timeout=False)

    context = _context("task_validate_awaiting_callbacks")

    result = awaiting_callbacks_exist(context)

    assert isinstance(result, RunPredicateFail)
    assert result.message == "No processes are awaiting a callback with a timeout"


def test_awaiting_callbacks_exist_short_circuits_on_uncompleted_instance(test_process, test_workflow) -> None:
    # An uncompleted instance of the task itself exists (test_process is CREATED), so the sweep must not start
    # even though there is an awaiting-callback process with a timeout to check.
    _awaiting_process(test_workflow, with_timeout=True)

    context = _context(test_workflow.name)

    result = awaiting_callbacks_exist(context)

    assert isinstance(result, RunPredicateFail)
    assert "uncompleted instance" in result.message
