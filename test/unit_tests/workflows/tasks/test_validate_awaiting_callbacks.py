# Copyright 2026 SURF.
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

"""Unit tests for the pure timeout helper of the awaiting-callback sweep task."""

from datetime import timedelta
from types import SimpleNamespace

import pytest

from orchestrator.core.utils.datetime import nowtz
from orchestrator.core.workflow import CALLBACK_TIMEOUT_KEY
from orchestrator.core.workflows.tasks.validate_awaiting_callbacks import _is_timed_out

NOW = nowtz()


def _process(*, state: dict | None = None, started_offset: timedelta | None = None, no_steps: bool = False):
    if no_steps:
        return SimpleNamespace(steps=[])
    started_at = None if started_offset is None else NOW - started_offset
    return SimpleNamespace(steps=[SimpleNamespace(state=state or {}, started_at=started_at)])


@pytest.mark.parametrize(
    "process,expected",
    [
        pytest.param(_process(no_steps=True), False, id="no-steps"),
        pytest.param(_process(state={}, started_offset=timedelta(hours=1)), False, id="no-timeout-key"),
        pytest.param(
            _process(state={CALLBACK_TIMEOUT_KEY: 300}, started_offset=None),
            False,
            id="no-started-at",
        ),
        pytest.param(
            _process(state={CALLBACK_TIMEOUT_KEY: 300}, started_offset=timedelta(seconds=120)),
            False,
            id="not-yet-expired",
        ),
        pytest.param(
            _process(state={CALLBACK_TIMEOUT_KEY: 300}, started_offset=timedelta(seconds=600)),
            True,
            id="expired",
        ),
    ],
)
def test_is_timed_out(process, expected) -> None:
    assert _is_timed_out(process, NOW) is expected
