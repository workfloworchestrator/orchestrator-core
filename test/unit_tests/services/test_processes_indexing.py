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

from orchestrator.core.services.processes import _safe_index_process
from orchestrator.core.workflow import Success


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


@patch("orchestrator.core.search.indexing.hooks.index_process_and_subscriptions")
def test_abort_process_indexes_on_exit(mock_hook):
    process_id = uuid4()
    result = Success({})

    with (
        patch("orchestrator.core.services.processes.load_process") as mock_load,
        patch("orchestrator.core.services.processes.abort_wf", return_value=result),
    ):
        mock_load.return_value.process_id = process_id

        from orchestrator.core.services.processes import abort_process

        assert abort_process(process=None, user="tester") is result

    mock_hook.assert_called_once_with(process_id, result)


@patch("orchestrator.core.search.indexing.hooks.index_process_and_subscriptions")
def test_fail_awaiting_process_indexes_on_exit(mock_hook):
    process_id = uuid4()
    result = Success({})

    with (
        patch("orchestrator.core.services.processes.load_process") as mock_load,
        patch("orchestrator.core.services.processes.fail_awaiting_wf", return_value=result),
    ):
        mock_load.return_value.process_id = process_id

        from orchestrator.core.services.processes import fail_awaiting_process

        assert fail_awaiting_process(process=None) is result

    mock_hook.assert_called_once_with(process_id, result)
