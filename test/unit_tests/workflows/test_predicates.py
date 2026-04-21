# Copyright 2019-2026 SURF.
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

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from orchestrator.core.db import ProcessTable, db
from orchestrator.core.workflow import (
    PredicateContext,
    ProcessStatus,
    RunPredicateFail,
    RunPredicatePass,
)
from orchestrator.core.workflows.predicates import no_uncompleted_instance


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

    context = MagicMock(spec=PredicateContext)
    context.workflow_key = test_workflow.name

    result = no_uncompleted_instance(context)

    assert isinstance(result, expected_type)
