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


from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from more_itertools import partition
from pydantic import BaseModel

from orchestrator.db.filters import Filter
from orchestrator.db.filters.filters import CallableErrorHandler
from orchestrator.db.sorting import Sort
from orchestrator.db.sorting.sorting import SortOrder
from orchestrator.settings import app_settings
from orchestrator.utils.helpers import camel_to_snake, to_camel

jobstores = {"default": SQLAlchemyJobStore(url=str(app_settings.DATABASE_URI))}

scheduler = BackgroundScheduler(jobstores=jobstores)


def scheduler_dispose_db_connections() -> None:
    jobstores["default"].engine.dispose()


@contextmanager
def get_paused_scheduler() -> Generator[BackgroundScheduler, Any, None]:
    scheduler.start(paused=True)

    try:
        yield scheduler
    finally:
        scheduler.shutdown(wait=False)
        scheduler_dispose_db_connections()


class ScheduledTask(BaseModel):
    id: str
    name: str | None = None
    next_run_time: datetime | None = None
    trigger: str


scheduled_task_keys = set(ScheduledTask.model_fields.keys())
scheduled_task_filter_keys = sorted(scheduled_task_keys | {to_camel(key) for key in scheduled_task_keys})
scheduled_task_sort_keys = scheduled_task_filter_keys


def scheduled_task_in_filter(job: ScheduledTask, filter_by: list[Filter]) -> bool:
    return any(f.value.lower() in getattr(job, camel_to_snake(f.field), "").lower() for f in filter_by)


def filter_scheduled_tasks(
    scheduled_tasks: list[ScheduledTask],
    handle_filter_error: CallableErrorHandler,
    filter_by: list[Filter] | None = None,
) -> list[ScheduledTask]:
    if not filter_by:
        return scheduled_tasks

    try:
        invalid_filters, valid_filters = partition(lambda x: x.field in scheduled_task_filter_keys, filter_by)

        if invalid_list := [item.field for item in invalid_filters]:
            handle_filter_error(
                "Invalid filter arguments", invalid_filters=invalid_list, valid_filter_keys=scheduled_task_filter_keys
            )

        valid_filter_list = list(valid_filters)
        return [task for task in scheduled_tasks if scheduled_task_in_filter(task, valid_filter_list)]
    except Exception as e:
        handle_filter_error(str(e))
        return []


def _invert(value: Any) -> Any:
    """Invert value for descending order."""
    if isinstance(value, (int, float)):
        return -value
    if isinstance(value, str):
        return tuple(-ord(c) for c in value)
    if isinstance(value, datetime):
        return -value.timestamp()
    return value


def sort_key(sort_field: str, sort_order: SortOrder) -> Any:
    def _sort_key(task: Any) -> Any:
        value = getattr(task, camel_to_snake(sort_field), None)
        if sort_field == "next_run_time" and value is None:
            return float("inf") if sort_order == SortOrder.ASC else float("-inf")
        return value if sort_order == SortOrder.ASC else _invert(value)

    return _sort_key


def sort_scheduled_tasks(
    scheduled_tasks: list[ScheduledTask], handle_sort_error: CallableErrorHandler, sort_by: list[Sort] | None = None
) -> list[ScheduledTask]:
    if not sort_by:
        return scheduled_tasks

    try:
        invalid_sorting, valid_sorting = partition(lambda x: x.field in scheduled_task_sort_keys, sort_by)
        if invalid_list := [item.field for item in invalid_sorting]:
            handle_sort_error(
                "Invalid sort arguments", invalid_sorting=invalid_list, valid_sort_keys=scheduled_task_sort_keys
            )

        valid_sort_list = list(valid_sorting)
        return sorted(
            scheduled_tasks, key=lambda task: tuple(sort_key(sort.field, sort.order)(task) for sort in valid_sort_list)
        )
    except Exception as e:
        handle_sort_error(str(e))
        return []


def default_error_handler(message: str, **context) -> None:  # type: ignore
    from orchestrator.graphql.utils.create_resolver_error_handler import _format_context

    raise ValueError(f"{message} {_format_context(context)}")


def get_scheduler_tasks(
    first: int = 10,
    after: int = 0,
    filter_by: list[Filter] | None = None,
    sort_by: list[Sort] | None = None,
    error_handler: CallableErrorHandler = default_error_handler,
) -> tuple[list[ScheduledTask], int]:
    with get_paused_scheduler() as pauzed_scheduler:
        scheduled_tasks = pauzed_scheduler.get_jobs()

    scheduled_tasks = filter_scheduled_tasks(scheduled_tasks, error_handler, filter_by)
    scheduled_tasks = sort_scheduled_tasks(scheduled_tasks, error_handler, sort_by)

    total = len(scheduled_tasks)
    paginated_tasks = scheduled_tasks[after : after + first + 1]

    return [
        ScheduledTask(
            id=task.id,
            name=task.name,
            next_run_time=task.next_run_time,
            trigger=str(task.trigger),
        )
        for task in paginated_tasks
    ], total
