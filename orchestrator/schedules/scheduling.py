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
from typing import TypeVar

from apscheduler.schedulers.base import BaseScheduler
from deprecated import deprecated

from orchestrator.schedules.scheduler import scheduler as default_scheduler  # your global scheduler instance

F = TypeVar("F", bound=Callable[..., object])


@deprecated(
    reason="We changed from scheduler to apscheduler which has its own decoractor, use `@scheduler.scheduled_job()` from `from orchestrator.scheduling.scheduler import scheduler`"
)
def scheduler(
    name: str,
    time_unit: str,
    period: int = 1,
    at: str | None = None,
    *,
    id: str | None = None,
    scheduler: BaseScheduler = default_scheduler,
) -> Callable[[F], F]:
    """APScheduler-compatible decorator to schedule a function.

    id is necessary with apscheduler, if left empty it takes the function name.

    - `time_unit = "hours", period = 12`  → every 12 hours
    - `time_unit = "day", at = "01:00"`   → every day at 1 AM
    """

    def decorator(func: F) -> F:
        job_id = id or func.__name__

        trigger = "interval"
        kwargs: dict[str, int] = {}
        if time_unit == "day" and at:
            trigger = "cron"
            try:
                hour, minute = map(int, at.split(":"))
            except ValueError:
                raise ValueError(f"Invalid time format for 'at': {at}, expected 'HH:MM'")

            kwargs = {
                "hour": hour,
                "minute": minute,
            }
        else:
            # Map string units to timedelta kwargs for IntervalTrigger
            unit_map = {
                "seconds": "seconds",
                "second": "seconds",
                "minutes": "minutes",
                "minute": "minutes",
                "hours": "hours",
                "hour": "hours",
                "days": "days",
                "day": "days",
            }

            interval_arg = unit_map.get(time_unit.lower(), time_unit.lower())
            kwargs = {interval_arg: period}

        scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=name,
            replace_existing=True,
            **kwargs,
        )

        return func

    return decorator
