# Copyright 2019-2026 SURF, GEANT, ESnet.
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

import datetime as dt

import pytest
from apscheduler.triggers.cron import CronTrigger

import orchestrator.core.forms.apscheduler_dow_fix as apscheduler_dow_fix_module
from orchestrator.core.forms.apscheduler_dow_fix import _translate_dow_for_apscheduler3, maybe_translate_dow


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("*", "*", id="wildcard"),
        pytest.param("*/2", "1,3,5,6", id="step-wildcard"),
        pytest.param("*/1", "0,1,2,3,4,5,6", id="step-wildcard-one"),
        pytest.param("*/7", "6", id="step-wildcard-seven"),
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
        # N/step: expand from N to 6 then shift, same as */step but starting at N
        pytest.param("0/2", "1,3,5,6", id="step-sunday-zero"),  # Sun,Tue,Thu,Sat->6,1,3,5 sorted->1,3,5,6
        pytest.param("7/2", "1,3,5,6", id="step-sunday-seven"),  # 7=Sunday alias->same as 0/2
        pytest.param("1/2", "0,2,4", id="step-monday"),  # Mon,Wed,Fri->0,2,4
        pytest.param("0/3", "2,5,6", id="step-sunday-zero-three"),  # Sun,Wed,Sat->6,2,5 sorted->2,5,6
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


def test_maybe_translate_dow_translates_when_v3():
    assert maybe_translate_dow("0") == "6"  # Sunday(0) -> APScheduler 3.x Sunday(6)


def test_maybe_translate_dow_passthrough_when_not_v3(monkeypatch):
    monkeypatch.setattr(apscheduler_dow_fix_module, "APSCHEDULER_V3", False)
    assert maybe_translate_dow("0") == "0"  # no translation on v4+


def test_apscheduler3_dow_numbering_canary():
    """Canary: fails when APScheduler fixes its day_of_week numbering to match crontab.

    APScheduler 3.x uses 0=Monday..6=Sunday instead of the crontab convention 0=Sunday..6=Saturday.
    The translation shim (_translate_dow_for_apscheduler3) exists solely because of this mismatch.
    When this test fails it means APScheduler has been updated to use crontab-compatible numbering (>= v4).
    Delete this module and remove the ``<4`` upper bound from pyproject.toml.
    """
    # In APScheduler 3.x, day_of_week=0 means Monday (not Sunday as in crontab).
    # Probe from a known Sunday: 2024-01-07.
    trigger = CronTrigger(day_of_week=0)
    next_fire = trigger.get_next_fire_time(None, dt.datetime(2024, 1, 7, 0, 0, tzinfo=dt.timezone.utc))
    assert next_fire is not None
    # If APScheduler 3.x behaviour holds, day_of_week=0 fires on Monday (2024-01-08), not Sunday.
    assert next_fire.weekday() == 0, (
        "APScheduler day_of_week=0 no longer means Monday — the crontab-to-APScheduler translation shim can be removed."
    )
