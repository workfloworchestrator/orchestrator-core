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

import logging

import pytest

from orchestrator.core.distlock import WrappedDistLockManager


def test_wrapped_no_wrappee_returns_none_for_method(caplog: pytest.LogCaptureFixture) -> None:
    wrapped = WrappedDistLockManager()
    with caplog.at_level(logging.WARNING, logger="orchestrator.core.distlock"):
        assert wrapped.connect_redis is None
    assert "No DistLockManager configured" in caplog.text
