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

import orchestrator.core.forms.scheduler_form as scheduler_form_module
from orchestrator.core.forms.scheduler_form import (
    _check_authorize,
    _cron_field_error,
    _translate_dow_for_apscheduler3,
    get_cron_kwargs,
    validate_cron,
)
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
            # crontab 1 = Monday, APScheduler 3.x 0 = Monday
            "0 8 * * 1",
            {"minute": "0", "hour": "8", "day": "*", "month": "*", "day_of_week": "0"},
            id="specific-monday",
        ),
        pytest.param(
            # crontab 2 = Tuesday, APScheduler 3.x 1 = Tuesday
            "0 8 * * 2",
            {"minute": "0", "hour": "8", "day": "*", "month": "*", "day_of_week": "1"},
            id="specific-tuesday",
        ),
        pytest.param(
            # crontab 0 = Sunday, APScheduler 3.x 6 = Sunday
            "0 8 * * 0",
            {"minute": "0", "hour": "8", "day": "*", "month": "*", "day_of_week": "6"},
            id="specific-sunday-zero",
        ),
        pytest.param(
            # crontab 7 = Sunday alias, APScheduler 3.x 6 = Sunday
            "0 8 * * 7",
            {"minute": "0", "hour": "8", "day": "*", "month": "*", "day_of_week": "6"},
            id="specific-sunday-seven",
        ),
        pytest.param(
            # crontab 1-5 = Mon-Fri, APScheduler 3.x 0-4 = Mon-Fri
            "0 9 * * 1-5",
            {"minute": "0", "hour": "9", "day": "*", "month": "*", "day_of_week": "0-4"},
            id="range-weekdays",
        ),
        pytest.param(
            # named days pass through unchanged
            "0 9 * * mon-fri",
            {"minute": "0", "hour": "9", "day": "*", "month": "*", "day_of_week": "mon-fri"},
            id="named-days",
        ),
        pytest.param(
            "*/15 * * * * *",
            {"second": "*/15", "minute": "*", "hour": "*", "day": "*", "month": "*", "day_of_week": "*"},
            id="6-field-seconds",
        ),
        pytest.param(
            # crontab 0-6 = all days, APScheduler 3.x 0-6 (full coverage, no inversion)
            "0 9 * * 0-6",
            {"minute": "0", "hour": "9", "day": "*", "month": "*", "day_of_week": "0-6"},
            id="range-all-days",
        ),
        pytest.param(
            # crontab 0-3 = Sun-Wed, split to avoid inverted APScheduler range
            "0 9 * * 0-3",
            {"minute": "0", "hour": "9", "day": "*", "month": "*", "day_of_week": "0-2,6"},
            id="range-sunday-start",
        ),
        pytest.param(
            # mixed named+numeric: "mon" passes through, "5" (Fri) → "4"
            "0 9 * * mon,5",
            {"minute": "0", "hour": "9", "day": "*", "month": "*", "day_of_week": "mon,4"},
            id="mixed-named-numeric",
        ),
        pytest.param(
            # crontab 0-3/2 = Sun,Tue stepped, shifted then sorted → "1,6"
            "0 9 * * 0-3/2",
            {"minute": "0", "hour": "9", "day": "*", "month": "*", "day_of_week": "1,6"},
            id="range-sunday-start-stepped",
        ),
    ],
)
def test_get_cron_kwargs(cron, expected):
    assert get_cron_kwargs({"cron": cron, "start_date": START_DATE}) == {"start_date": START_DATE, **expected}


@pytest.mark.parametrize("cron", ["* * * *", "* * * * * * *"], ids=["4-fields", "7-fields"])
def test_get_cron_kwargs_rejects_wrong_field_count(cron):
    with pytest.raises(ValueError):
        get_cron_kwargs({"cron": cron, "start_date": START_DATE})


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("*", "*", id="wildcard"),
        pytest.param("*/2", "*/2", id="step-wildcard"),
        pytest.param("1", "0", id="monday"),
        pytest.param("2", "1", id="tuesday"),
        pytest.param("6", "5", id="saturday"),
        pytest.param("0", "6", id="sunday-zero"),
        pytest.param("7", "6", id="sunday-seven"),
        pytest.param("1-5", "0-4", id="range-weekdays"),
        pytest.param("1-5/2", "0-4/2", id="range-weekdays-step"),
        pytest.param("3-7", "2-6", id="range-with-sunday-alias"),
        pytest.param("0-6", "0-6", id="range-all-days"),
        pytest.param("0-7", "0-6", id="range-all-days-with-alias"),
        pytest.param("0-3", "0-2,6", id="range-sunday-start-partial"),
        pytest.param("0-5", "0-4,6", id="range-sunday-start-to-friday"),
        pytest.param("0-1", "0,6", id="range-sunday-monday"),
        pytest.param("0-6/2", "1,3,5,6", id="range-all-days-stepped"),
        pytest.param("0-3/2", "1,6", id="range-sunday-start-stepped"),
        pytest.param("0,6", "6,5", id="list-sunday-saturday"),
        pytest.param("mon,5", "mon,4", id="mixed-named-numeric"),
        pytest.param("mon,7", "mon,6", id="mixed-named-sunday-alias"),
        pytest.param("0,tue", "6,tue", id="mixed-numeric-named"),
        pytest.param("mon-fri", "mon-fri", id="named-range"),
        pytest.param("tue", "tue", id="named-single"),
    ],
)
def test_translate_dow_for_apscheduler3(value, expected):
    assert _translate_dow_for_apscheduler3(value) == expected


@pytest.mark.parametrize(
    "cron",
    [
        "* * * * *",
        "0-59 * * * *",
        "1,15,30 * * * *",
        "0 9-17 * * 1-5",
        "*/15 * * * * *",
        "0 8 * * 7",  # crontab Sunday alias (7)
        "0 8 * * 0",  # crontab 0 (Sunday)
        "0 9 * * 0-6",  # full crontab range: translates to APScheduler "0-6"
        "0 9 * * mon,5",  # mixed named+numeric: "mon" passes through, 5→4
        "0 9 * * 0-3",  # inverted range starting at Sunday: splits to "0-2,6"
    ],
    ids=[
        "wildcards",
        "range",
        "list",
        "workhours",
        "6-field-seconds",
        "sunday-seven",
        "sunday-zero",
        "every-day-range",
        "mixed-named-numeric",
        "sunday-start-range",
    ],
)
def test_validate_cron_accepts_valid(cron):
    assert validate_cron(cron) == cron


@pytest.mark.parametrize(
    "cron",
    [
        "60 * * * * *",
        "60 * * * *",
        "* 24 * * *",
        "* * 0 * *",
        "* * 32 * *",
        "* * * 0 *",
        "* * * 13 *",
        "* * * * 8",
        "* * * *",
        "* * * * * * *",
    ],
    ids=[
        "second-oob",
        "minute-oob",
        "hour-oob",
        "day-zero",
        "day-oob",
        "month-zero",
        "month-oob",
        "day_of_week-oob",
        "4-fields",
        "7-fields",
    ],
)
def test_validate_cron_rejects_invalid(cron):
    with pytest.raises(ValueError):
        validate_cron(cron)


@pytest.mark.parametrize(
    "cron,expected_fields",
    [
        pytest.param("61 61 * * * *", ["second '61'", "minute '61'"], id="two-bad-6-field"),
        pytest.param("50-52 59 24 * * *", ["hour '24'"], id="hour-only-6-field"),
        pytest.param("61 24 * * *", ["minute '61'", "hour '24'"], id="two-bad-5-field"),
    ],
)
def test_validate_cron_error_names_all_bad_fields(cron, expected_fields):
    with pytest.raises(ValueError) as exc_info:
        validate_cron(cron)
    message = str(exc_info.value)
    assert all(field in message for field in expected_fields)


# If APScheduler ever gets a v4 release
@pytest.mark.parametrize(
    ("value", "expected_error"),
    [
        pytest.param("1-5", None, id="range-no-translation"),
        pytest.param("0", None, id="sunday-zero-no-translation"),
        # Without translation, "7" is passed raw to APScheduler 3.x which rejects it (max 6)
        pytest.param("7", "error", id="sunday-seven-no-translation-fails"),
    ],
)
def test_cron_field_error_skips_translation_when_not_v3(monkeypatch, value, expected_error):
    monkeypatch.setattr(scheduler_form_module, "_APSCHEDULER_V3", False)
    result = _cron_field_error("day_of_week", value)
    if expected_error is None:
        assert result is None
    else:
        assert isinstance(result, str)


@pytest.mark.parametrize(
    ("cron", "expected_dow"),
    [
        pytest.param("0 8 * * 1", "1", id="monday-untranslated"),
        pytest.param("0 8 * * 1-5", "1-5", id="range-untranslated"),
        pytest.param("0 8 * * 0", "0", id="sunday-zero-untranslated"),
    ],
)
def test_get_cron_kwargs_skips_translation_when_not_v3(monkeypatch, cron, expected_dow):
    monkeypatch.setattr(scheduler_form_module, "_APSCHEDULER_V3", False)
    result = get_cron_kwargs({"cron": cron, "start_date": START_DATE})
    assert result["day_of_week"] == expected_dow
