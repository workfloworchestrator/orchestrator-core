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

"""Unit tests for WrappedSession accessor methods: is_commit_disabled, enable_commit, disable_commit."""

import pytest

from orchestrator.core.db.database import WrappedSession


@pytest.mark.parametrize(
    "info,expected",
    [
        pytest.param({"disabled": True}, True, id="disabled-true"),
        pytest.param({"disabled": False}, False, id="disabled-false"),
        pytest.param({}, False, id="disabled-unset"),
        pytest.param({"disabled": None}, False, id="disabled-none"),
        pytest.param({"disabled": 1}, False, id="disabled-truthy-non-bool"),
        pytest.param({"disabled": "true"}, False, id="disabled-string-non-bool"),
    ],
)
def test_is_commit_disabled(info: dict, expected: bool) -> None:
    session = WrappedSession(info=info)
    assert session.is_commit_disabled() is expected


def test_disable_commit_sets_flag_true() -> None:
    session = WrappedSession(info={"disabled": False})
    session.disable_commit()
    assert session.info["disabled"] is True
    assert session.is_commit_disabled() is True


def test_enable_commit_sets_flag_false() -> None:
    session = WrappedSession(info={"disabled": True})
    session.enable_commit()
    assert session.info["disabled"] is False
    assert session.is_commit_disabled() is False


def test_disable_then_enable_round_trip() -> None:
    session = WrappedSession(info={"disabled": False})
    session.disable_commit()
    session.enable_commit()
    assert session.is_commit_disabled() is False


def test_disable_commit_is_idempotent() -> None:
    session = WrappedSession(info={"disabled": True})
    session.disable_commit()
    assert session.is_commit_disabled() is True


def test_enable_commit_is_idempotent() -> None:
    session = WrappedSession(info={"disabled": False})
    session.enable_commit()
    assert session.is_commit_disabled() is False
