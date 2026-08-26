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
from unittest.mock import call, patch
from uuid import uuid4

import pytest

from orchestrator.core.services import processes as processes_module
from orchestrator.core.services.processes import _run_process_async, _safe_index_process
from orchestrator.core.settings import ExecutorType, app_settings, llm_settings
from orchestrator.core.workflow import Process as WFProcess
from orchestrator.core.workflow import Success

pytestmark = pytest.mark.search


@patch("orchestrator.core.search.indexing.hooks.index_process_and_subscriptions")
def test_safe_index_process_calls_hook(mock_hook):
    process_id = uuid4()
    result = Success({})

    _safe_index_process(process_id, result)

    mock_hook.assert_called_once_with(process_id, result)


def test_safe_index_process_is_noop_without_search_extra(monkeypatch):
    # A None entry in sys.modules makes the import raise ImportError, simulating a missing extra.
    monkeypatch.setitem(sys.modules, "orchestrator.core.search.indexing.hooks", None)

    _safe_index_process(uuid4(), Success({}))  # must not raise


@pytest.mark.parametrize(
    "wf_attr,call_attr,call_kwargs",
    [
        pytest.param("abort_wf", "abort_process", {"process": None, "user": "tester"}, id="abort"),
        pytest.param("fail_awaiting_wf", "fail_awaiting_process", {"process": None}, id="fail-awaiting"),
    ],
)
@patch("orchestrator.core.search.indexing.hooks.index_process_and_subscriptions")
def test_synchronous_call_sites_index_on_exit_in_a_fresh_scope(mock_hook, wf_attr, call_attr, call_kwargs):
    """Both synchronous exit paths must index in their own scope, not the caller's live session.

    A caller-session query error inside indexing would otherwise leave that session needing a
    rollback the caller never issues — for `fail_awaiting_process` that caller is a step in the
    sweep workflow, which keeps using the same session for its remaining steps.
    """
    process_id = uuid4()
    result = Success({})

    with (
        patch("orchestrator.core.services.processes.load_process") as mock_load,
        patch(f"orchestrator.core.services.processes.{wf_attr}", return_value=result),
        patch("orchestrator.core.services.processes.db") as mock_db,
    ):
        mock_load.return_value.process_id = process_id
        mock_db.database_scope.return_value.__enter__ = lambda self: mock_db
        mock_db.database_scope.return_value.__exit__ = lambda self, *exc: None

        assert getattr(processes_module, call_attr)(**call_kwargs) is result

        mock_db.database_scope.assert_called_once()

    mock_hook.assert_called_once_with(process_id, result)


@pytest.mark.parametrize(
    "workflow_raises,expect_indexed",
    [
        pytest.param(False, True, id="committed-result-is-indexed"),
        pytest.param(True, False, id="lost-database-access-skips-indexing"),
    ],
)
@patch("orchestrator.core.search.indexing.hooks.index_process_and_subscriptions")
def test_run_process_async_indexes_only_while_the_session_is_alive(mock_hook, workflow_raises, expect_indexed):
    """Indexing runs inside the database scope, so the failure path that loses the session must skip it."""
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

    assert mock_hook.call_args_list == ([call(process_id, result)] if expect_indexed else [])


@patch("orchestrator.core.search.indexing.hooks.index_process_and_subscriptions")
def test_run_process_async_strict_indexing_failure_is_not_masked_as_workflow_failure(mock_hook, monkeypatch):
    """Strict mode exists to surface indexing bugs, so the workflow's own error handler must not eat them."""
    monkeypatch.setattr(llm_settings, "SEARCH_INDEXING_STRICT", True)
    mock_hook.side_effect = RuntimeError("index exploded")
    process_id = uuid4()
    result = Success({})

    with (
        patch("orchestrator.core.services.processes.db"),
        patch("orchestrator.core.services.processes._db_log_process_ex") as mock_log_ex,
        patch("orchestrator.core.services.processes.logger") as mock_logger,
        patch.object(app_settings, "EXECUTOR", ExecutorType.WORKER),
        pytest.raises(RuntimeError, match="index exploded"),
    ):
        _run_process_async(process_id, lambda: result)

    # The workflow itself never failed, so neither the DB-loss logger nor its process log may fire.
    mock_log_ex.assert_not_called()
    assert not any("Unknown workflow failure" in str(c) for c in mock_logger.exception.call_args_list)
