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

"""Integration tests for the default parallel executor.

Lives under integration_tests because :func:`_exec_parallel_branches` opens a
``db.database_scope()`` for each branch, which requires a real DB connection.
"""

from orchestrator.core.workflow import (
    StepList,
    _exec_parallel_branches,
    process_stat_var,
    step,
)


@step("Step A")
def _step_a() -> dict:
    return {"a": 1}


@step("Step B")
def _step_b() -> dict:
    return {"b": 2}


def test_threadpool_executor_is_default(db_session) -> None:  # noqa: ARG001 — fixture needed for db.database_scope
    # Clear any stale process context from previous tests so _exec_parallel_branches
    # runs without fork-step creation (process_stat_var=None skips the DB write).
    token = process_stat_var.set(None)  # type: ignore[arg-type]
    try:
        result = _exec_parallel_branches(
            branches=[StepList([_step_a]), StepList([_step_b])],
            initial_state={},
            name="test",
        )
    finally:
        process_stat_var.reset(token)
    assert result.issuccess()
