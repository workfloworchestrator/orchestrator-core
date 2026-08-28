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

"""Tests for process-exit indexing wiring in the processes service."""

import sys
from unittest.mock import patch
from uuid import uuid4

import pytest

from orchestrator.core.services.processes import _run_process_async, _safe_index_process
from orchestrator.core.settings import ExecutorType, app_settings, llm_settings
from orchestrator.core.workflow import Process as WFProcess
from orchestrator.core.workflow import Success

pytestmark = pytest.mark.search


def test_safe_index_process_is_noop_without_search_extra(monkeypatch):
    # A None entry in sys.modules makes the import raise ImportError, simulating a missing extra.
    monkeypatch.setitem(sys.modules, "orchestrator.core.search.indexing.hooks", None)

    _safe_index_process(uuid4(), Success({}))  # must not raise


# The synchronous exit paths (abort, callback timeout) index in their own database scope so a
# failing indexing query cannot leave the caller's session needing a rollback. That invariant is
# about a real session, so it is covered against a real one by
# test_indexing_failure_leaves_the_callers_session_usable in
# test/integration_tests/services/test_indexing_on_exit.py.


@pytest.mark.parametrize(
    "workflow_raises",
    [
        pytest.param(False, id="successful-result-is-indexed"),
        pytest.param(True, id="failed-result-is-indexed"),
    ],
)
@patch("orchestrator.core.search.indexing.hooks.index_process_and_subscriptions")
def test_run_process_async_indexes_after_workflow_commits(mock_hook, workflow_raises):
    """A live session always results in fresh-scope indexing after the workflow scope closes.

    When the workflow raises, _db_log_process_ex commits FAILED and its result is indexed
    through the same fresh scope as a successful result. Only failure of the workflow's
    database scope itself skips indexing.
    """
    process_id = uuid4()
    result = Success({})

    def workflow() -> WFProcess:
        if workflow_raises:
            raise RuntimeError("lost the database")
        return result

    with (
        patch("orchestrator.core.services.processes.db"),
        patch("orchestrator.core.services.processes._db_log_process_ex"),
        patch.object(app_settings, "EXECUTOR", ExecutorType.WORKER),
    ):
        assert _run_process_async(process_id, workflow) == process_id

    assert mock_hook.call_count == 1
    assert mock_hook.call_args[0][0] == process_id


@pytest.mark.parametrize(
    "workflow_raises",
    [
        pytest.param(False, id="successful-workflow"),
        pytest.param(True, id="failed-workflow"),
    ],
)
@patch("orchestrator.core.search.indexing.hooks.index_process_and_subscriptions")
def test_run_process_async_strict_indexing_failure_is_not_masked_as_workflow_failure(
    mock_hook, monkeypatch, workflow_raises
):
    """Strict mode lets indexing failures escape after either workflow outcome."""
    monkeypatch.setattr(llm_settings, "SEARCH_INDEXING_STRICT", True)
    mock_hook.side_effect = RuntimeError("index exploded")
    process_id = uuid4()

    def workflow() -> WFProcess:
        if workflow_raises:
            raise RuntimeError("workflow exploded")
        return Success({})

    with (
        patch("orchestrator.core.services.processes.db"),
        patch("orchestrator.core.services.processes._db_log_process_ex"),
        patch("orchestrator.core.services.processes.logger") as mock_logger,
        patch.object(app_settings, "EXECUTOR", ExecutorType.WORKER),
        pytest.raises(RuntimeError, match="index exploded"),
    ):
        _run_process_async(process_id, workflow)

    assert not any("Unknown workflow failure" in str(c) for c in mock_logger.exception.call_args_list)
