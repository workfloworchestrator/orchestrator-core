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

import pytest

from orchestrator.core.forms.scheduler_form import _check_authorize, get_cron_kwargs
from orchestrator.core.utils.auth import AuthContext
from orchestrator.core.workflow import begin, done, step, workflow


@step("noop")
def noop():
    return {}


async def allow_all(context: AuthContext) -> bool:
    return True


async def deny_all(context: AuthContext) -> bool:
    return False


async def allow_by_username(context: AuthContext) -> bool:
    if not context.user:
        return False
    return context.user.user_name == "admin"


class FakeUser:
    def __init__(self, name: str):
        self._name = name

    @property
    def user_name(self) -> str:
        return self._name


@pytest.fixture()
def allowed_workflow():
    @workflow(authorize_callback=allow_all)
    def allowed_wf():
        return begin >> noop >> done

    return allowed_wf


@pytest.fixture()
def denied_workflow():
    @workflow(authorize_callback=deny_all)
    def denied_wf():
        return begin >> noop >> done

    return denied_wf


@pytest.fixture()
def username_workflow():
    @workflow(authorize_callback=allow_by_username)
    def username_wf():
        return begin >> noop >> done

    return username_wf


async def test_check_authorize_allows(allowed_workflow):
    assert await _check_authorize(allowed_workflow, None) is True


async def test_check_authorize_denies(denied_workflow):
    assert await _check_authorize(denied_workflow, None) is False


async def test_check_authorize_passes_auth_context(username_workflow):
    assert await _check_authorize(username_workflow, FakeUser("admin")) is True
    assert await _check_authorize(username_workflow, FakeUser("nobody")) is False
    assert await _check_authorize(username_workflow, None) is False


START_DATE = object()  # get_cron_kwargs passes start_date through unchanged


@pytest.mark.parametrize(
    ("cron", "expected"),
    [
        pytest.param(
            "* * * * *",
            {"minute": "*", "hour": "*", "day": "*", "month": "*", "day_of_week": "*"},
            id="5-field-wildcards",
        ),
        pytest.param(
            "0-59 * * * *",
            {"minute": "0-59", "hour": "*", "day": "*", "month": "*", "day_of_week": "*"},
            id="range",
        ),
        pytest.param(
            "1,15,30 * * * *",
            {"minute": "1,15,30", "hour": "*", "day": "*", "month": "*", "day_of_week": "*"},
            id="list",
        ),
        pytest.param(
            "0 8 * * 1",
            {"minute": "0", "hour": "8", "day": "*", "month": "*", "day_of_week": "1"},
            id="specific",
        ),
        pytest.param(
            "*/15 * * * * *",
            {"second": "*/15", "minute": "*", "hour": "*", "day": "*", "month": "*", "day_of_week": "*"},
            id="6-field-seconds",
        ),
    ],
)
def test_get_cron_kwargs(cron, expected):
    assert get_cron_kwargs({"cron": cron, "start_date": START_DATE}) == {"start_date": START_DATE, **expected}


@pytest.mark.parametrize("cron", ["* * * *", "* * * * * * *"], ids=["4-fields", "7-fields"])
def test_get_cron_kwargs_rejects_wrong_field_count(cron):
    with pytest.raises(ValueError):
        get_cron_kwargs({"cron": cron, "start_date": START_DATE})
