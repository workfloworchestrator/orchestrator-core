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

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from orchestrator.core.services.parallel import _atomic_increment_completed, _join_and_resume


@pytest.mark.parametrize(
    "return_val",
    [
        pytest.param(1, id="first-increment"),
        pytest.param(3, id="mid-increment"),
    ],
)
@patch("orchestrator.core.services.parallel.db")
def test_atomic_increment_completed_returns_count_and_total(mock_db: MagicMock, return_val: int) -> None:
    # TODO remove test of private function, assert the behavior as part of tests of higher level functions
    fork_step_id = uuid4()
    mock_result = MagicMock()
    mock_result.one.return_value = (return_val, 5)
    mock_db.session.execute.return_value = mock_result

    completed, total = _atomic_increment_completed(fork_step_id)
    assert completed == return_val
    assert total == 5
    mock_db.session.commit.assert_called_once()


@patch("orchestrator.core.services.parallel.db")
def test_atomic_increment_executes_update_on_process_steps(mock_db: MagicMock) -> None:
    # TODO remove test of private function, assert the behavior as part of tests of higher level functions
    fork_step_id = uuid4()
    mock_result = MagicMock()
    mock_result.one.return_value = (2, 4)
    mock_db.session.execute.return_value = mock_result

    _atomic_increment_completed(fork_step_id)

    mock_db.session.execute.assert_called_once()
    stmt = mock_db.session.execute.call_args[0][0]
    assert "process_steps" in str(stmt)


@patch("orchestrator.core.services.parallel.db")
def test_join_and_resume_raises_when_fork_step_is_missing(mock_db: MagicMock) -> None:
    """A missing fork step must not be skipped: the process would resume with the parallel step unresolved."""
    process_id = uuid4()
    fork_step_id = uuid4()
    mock_db.session.get.return_value = None

    with pytest.raises(ValueError, match=f"Fork step {fork_step_id} not found"):
        _join_and_resume(process_id=process_id, fork_step_id=fork_step_id, initial_state={}, user="test_user")

    mock_db.session.commit.assert_not_called()


@patch("orchestrator.core.services.parallel.db")
@patch("orchestrator.core.services.parallel.logger")
def test_join_and_resume_logs_ids_when_fork_step_is_missing(mock_logger: MagicMock, mock_db: MagicMock) -> None:
    """The stuck process must be findable from the logs: log the process id and fork step id before raising."""
    process_id = uuid4()
    fork_step_id = uuid4()
    mock_db.session.get.return_value = None

    with pytest.raises(ValueError):
        _join_and_resume(process_id=process_id, fork_step_id=fork_step_id, initial_state={}, user="test_user")

    mock_logger.error.assert_called_once_with(
        "Fork step not found while joining parallel branches",
        process_id=str(process_id),
        fork_step_id=str(fork_step_id),
    )
