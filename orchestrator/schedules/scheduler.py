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


from datetime import datetime
from typing import Any

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from pydantic import BaseModel

from orchestrator.db.filters import Filter
from orchestrator.db.sorting import Sort
from orchestrator.db.sorting.sorting import SortOrder
from orchestrator.settings import app_settings

jobstores = {"default": SQLAlchemyJobStore(url=str(app_settings.DATABASE_URI))}

scheduler = BackgroundScheduler(jobstores=jobstores)


class ScheduledJob(BaseModel):
    id: str
    name: str | None = None
    next_run_time: datetime | None = None
    trigger: str


def get_scheduler_jobs(
    first: int = 10, after: int = 0, filter_by: list[Filter] | None = None, sort_by: list[Sort] | None = None
) -> tuple[list[ScheduledJob], int]:
    scheduler.start(paused=True)
    jobs = scheduler.get_jobs()
    scheduler.shutdown()

    # Filter by search string
    if filter_by:
        filtered_jobs = jobs
        for filter in filter_by:
            search_lower = filter.value.lower()
            filtered_jobs = [
                job for job in filtered_jobs if search_lower in getattr(job, filter.field.lower(), "").lower()
            ]
        jobs = filtered_jobs

    if sort_by:
        # Sort jobs
        def sort_key(sort_field: str, sort_order: SortOrder) -> Any:
            def _sort_key(job: Any) -> Any:
                value = getattr(job, sort_field, None)
                if sort_field == "next_run_time" and value is None:
                    return float("inf") if sort_order == SortOrder.ASC else float("-inf")
                return value

            return _sort_key

        for sort in sort_by:
            jobs.sort(
                key=sort_key(sort_field=sort.field, sort_order=sort.order), reverse=(sort.order == SortOrder.DESC)
            )

    total = len(jobs)
    paginated_jobs = jobs[after : after + first + 1]

    return [
        ScheduledJob(
            id=job.id,
            name=job.name,
            next_run_time=getattr(job, "next_run_time", None),
            trigger=str(job.trigger),
        )
        for job in paginated_jobs
    ], total
