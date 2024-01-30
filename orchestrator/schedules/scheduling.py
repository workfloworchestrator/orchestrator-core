# Copyright 2019-2020 SURF.
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

from collections.abc import Callable
from typing import Protocol, cast

from schedule import CancelJob


class SchedulingFunction(Protocol):
    __name__: str
    name: str
    time_unit: str
    period: int | None
    at: str | None

    def __call__(self) -> CancelJob | None: ...


def scheduler(
    name: str, time_unit: str, period: int = 1, at: str | None = None
) -> Callable[[Callable[[], CancelJob | None]], SchedulingFunction]:
    """Create schedule.

    Either specify the period or the at. Examples:
    time_unit = "hours", period = 12 -> will run every 12 hours
    time_unit = "day", at="01:00" -> will run every day at 1 o'clock
    """

    def _scheduler(f: Callable[[], CancelJob | None]) -> SchedulingFunction:
        schedule = cast(SchedulingFunction, f)
        schedule.name = name
        schedule.time_unit = time_unit
        schedule.period = period
        schedule.at = at
        return schedule

    return _scheduler
