# Copyright 2019-2020 SURF, GÉANT.
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

"""Tests for Authorizers callback delegation logic and get_authorizers singleton."""

import pytest

from orchestrator.settings import Authorizers, get_authorizers


@pytest.mark.parametrize(
    "method_name",
    [
        pytest.param("authorize_callback", id="authorize"),
        pytest.param("retry_auth_callback", id="retry-auth"),
    ],
)
@pytest.mark.asyncio
async def test_callback_returns_true_when_no_internal_callback(method_name: str) -> None:
    auth = Authorizers()
    result = await getattr(auth, method_name)(None)
    assert result is True


@pytest.mark.parametrize(
    "method_name,field_name",
    [
        pytest.param("authorize_callback", "internal_authorize_callback", id="authorize"),
        pytest.param("retry_auth_callback", "internal_retry_auth_callback", id="retry-auth"),
    ],
)
@pytest.mark.asyncio
async def test_callback_delegates_to_internal_callback(method_name: str, field_name: str) -> None:
    async def _deny(user: object) -> bool:
        return False

    auth = Authorizers(**{field_name: _deny})
    result = await getattr(auth, method_name)(None)
    assert result is False


def test_get_authorizers_returns_same_singleton() -> None:
    assert get_authorizers() is get_authorizers()
