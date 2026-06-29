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
import json
import time
from collections.abc import Iterator
from typing import cast

import typer
from apscheduler.job import Job
from redis import Redis

from orchestrator.core.db import db
from orchestrator.core.schedules.scheduler import (
    get_all_scheduler_tasks,
    get_scheduler,
    get_scheduler_task,
)
from orchestrator.core.schedules.service import (
    SCHEDULER_QUEUE,
    add_unique_scheduled_task_to_queue,
    workflow_scheduler_queue,
)
from orchestrator.core.schemas.schedules import APSchedulerJobCreate
from orchestrator.core.services.workflows import get_workflow_by_name
from orchestrator.core.settings import app_settings
from orchestrator.core.utils.redis_client import create_redis_client

app: typer.Typer = typer.Typer()


@app.command()
def run() -> None:
    """Starts the scheduler in the foreground.

    While running, this process will:

      * Periodically wake up when the next schedule is due for execution, and run it
      * Process schedule changes made through the schedule API
    """

    def _get_scheduled_task_item_from_queue(redis_conn: Redis) -> tuple[str, bytes] | None:
        """Get an item from the Redis Queue for scheduler tasks."""
        try:
            return redis_conn.brpop(SCHEDULER_QUEUE, timeout=1)
        except ConnectionError as e:
            typer.echo(f"There was a connection error with Redis. Retrying in 3 seconds... {e}")
            time.sleep(3)
        except Exception as e:
            typer.echo(f"There was an unexpected error with Redis. Retrying in 1 second... {e}")
            time.sleep(1)

        return None

    with get_scheduler() as scheduler_connection:
        redis_connection = create_redis_client(app_settings.CACHE_URI.get_secret_value())
        while True:
            item = _get_scheduled_task_item_from_queue(redis_connection)
            if not item:
                continue

            with db.database_scope():
                workflow_scheduler_queue(item, scheduler_connection)


def _to_schedule_row(task: Job, *, api_managed_ids: set[str], verbose: bool) -> list[str]:
    source = "API" if task.id in api_managed_ids else "decorator"
    run_time = str(task.next_run_time.replace(microsecond=0))

    def values() -> Iterator[str]:
        yield task.id  # id
        yield task.name  # name
        yield source  # source
        yield str(run_time)  # next run time
        yield str(task.trigger)  # trigger
        if verbose:
            yield json.dumps(task.kwargs, indent=2)  # kwargs

    return list(values())


@app.command()
def show_schedule(
    verbose: bool = typer.Option(False, "-v", help="Show additional details, such as job kwargs"),
) -> None:
    """The `show-schedule` command shows an overview of the scheduled jobs."""
    from rich.console import Console
    from rich.table import Table

    from orchestrator.core.schedules.service import get_linker_entries_by_schedule_ids

    console = Console()

    table = Table(title="Scheduled Tasks", show_lines=verbose)
    table.add_column("id", no_wrap=True)
    table.add_column("name")
    table.add_column("source")
    table.add_column("next run time")
    table.add_column("trigger")
    if verbose:
        table.add_column("kwargs")

    scheduled_tasks = get_all_scheduler_tasks()
    _schedule_ids = [task.id for task in scheduled_tasks]
    api_managed = {str(i.schedule_id) for i in get_linker_entries_by_schedule_ids(_schedule_ids)}

    # Sort by next run time, then by name
    scheduled_tasks.sort(key=lambda x: (x.next_run_time, x.name))

    for task in scheduled_tasks:
        table.add_row(*_to_schedule_row(task, api_managed_ids=api_managed, verbose=verbose))

    console.print(table)


@app.command()
def force(task_id: str) -> None:
    """Force the execution of (a) scheduler(s) based on a schedule ID.

    Use the `show-schedule` command to determine the ID of the schedule to execute.

    CLI Arguments:
        ```sh
        Arguments:
            SCHEDULE_ID  ID of the schedule to execute
        ```
    """
    task = get_scheduler_task(task_id)

    if not task:
        typer.echo(f"Task '{task_id}' not found.")
        raise typer.Exit(code=1)

    typer.echo(f"Running Task [{task.id}] now...")
    try:
        task.func(*task.args or (), **task.kwargs or {})
        typer.echo("Task executed successfully.")
    except Exception as e:
        typer.echo(f"Task execution failed: {e}")
        raise typer.Exit(code=1)


@app.command()
def load_initial_schedule(
    recreate: bool = typer.Option(False, help="Whether to delete any existing schedules before creating"),
) -> None:
    """The `load-initial-schedule` command loads the initial schedule using the scheduler API.

    The initial schedules are:
      - Task Resume Workflows
      - Task Clean Up Tasks
      - Task Validate Subscriptions
      - Task Validate Products
      - Task Validate Awaiting Callbacks

    By default, this command is idempotent since v4.7.1 when the scheduler is running.
    The schedules are only created when they do not already exist in the database.
    This behavior can be altered through the --recreate option.
    """
    initial_schedules = [
        {
            "name": "Task Resume Workflows",
            "workflow_name": "task_resume_workflows",
            "workflow_id": "",
            "trigger": "interval",
            "trigger_kwargs": {"hours": 1},
        },
        {
            "name": "Task Clean Up Tasks",
            "workflow_name": "task_clean_up_tasks",
            "workflow_id": "",
            "trigger": "interval",
            "trigger_kwargs": {"hours": 6},
        },
        {
            "name": "Task Validate Subscriptions",
            "workflow_name": "task_validate_subscriptions",
            "workflow_id": "",
            "trigger": "cron",
            "trigger_kwargs": {"hour": 0, "minute": 10},
        },
        {
            "name": "Task Validate Products",
            "workflow_name": "task_validate_products",
            "workflow_id": "",
            "trigger": "cron",
            "trigger_kwargs": {"hour": 2, "minute": 30},
        },
        {
            "name": "Task Validate Awaiting Callbacks",
            "workflow_name": "task_validate_awaiting_callbacks",
            "workflow_id": "",
            "trigger": "interval",
            "trigger_kwargs": {"seconds": 30},
        },
    ]

    for schedule in initial_schedules:
        # enrich with workflow id
        workflow_name = cast(str, schedule.get("workflow_name"))
        workflow = get_workflow_by_name(workflow_name)

        if not workflow:
            typer.echo(f"Workflow '{schedule['workflow_name']}' not found. Skipping schedule.")
            continue

        schedule["workflow_id"] = workflow.workflow_id

        typer.echo(f"Initial Schedule: {schedule}")
        payload = APSchedulerJobCreate.model_validate(schedule)
        add_unique_scheduled_task_to_queue(payload, recreate=recreate)
