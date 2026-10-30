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

from orchestrator.core.services.parallel import _atomic_increment_completed


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
