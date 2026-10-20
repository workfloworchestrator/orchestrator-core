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

"""Helpers for testing orchestrators built on orchestrator-core.

Install them with the ``testing`` extra: ``pip install orchestrator-core[testing]``.

- The workflow helpers below (``run_workflow``, ``assert_complete``, ...) are importable from this package and do not
  need pytest.
- :mod:`orchestrator.core.testing.fixtures` is a pytest plugin with database, app and test client fixtures. Load it
  with ``pytest_plugins = ["orchestrator.core.testing.fixtures"]`` in your root ``conftest.py``.
- :mod:`orchestrator.core.testing.services` resolves Postgres and Redis from the environment or testcontainers.
"""

from orchestrator.core.testing.workflows import (
    StepLog,
    WorkflowInstanceForTests,
    assert_aborted,
    assert_assignee,
    assert_awaiting_callback,
    assert_complete,
    assert_failed,
    assert_state,
    assert_state_equal,
    assert_step_name,
    assert_success,
    assert_suspended,
    assert_waiting,
    delete_workflow,
    extract_error,
    extract_state,
    resume_workflow,
    run_form_generator,
    run_workflow,
    store_workflow,
)

__all__ = [
    "StepLog",
    "WorkflowInstanceForTests",
    "assert_aborted",
    "assert_assignee",
    "assert_awaiting_callback",
    "assert_complete",
    "assert_failed",
    "assert_state",
    "assert_state_equal",
    "assert_step_name",
    "assert_success",
    "assert_suspended",
    "assert_waiting",
    "delete_workflow",
    "extract_error",
    "extract_state",
    "resume_workflow",
    "run_form_generator",
    "run_workflow",
    "store_workflow",
]
