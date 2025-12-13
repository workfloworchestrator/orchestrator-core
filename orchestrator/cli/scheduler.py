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
import time
from typing import cast

import typer
from redis import Redis

from orchestrator.schedules.scheduler import (
    get_all_scheduler_tasks,
    get_scheduler,
    get_scheduler_task,
)
from orchestrator.schedules.service import (
    SCHEDULER_QUEUE,
    add_scheduled_task_to_queue,
    workflow_scheduler_queue,
)
from orchestrator.schemas.schedules import APSchedulerJobCreate
from orchestrator.services.workflows import get_workflow_by_name
from orchestrator.settings import app_settings
from orchestrator.utils.redis_client import create_redis_client

app: typer.Typer = typer.Typer()


@app.command()
def run() -> None:
    """Start scheduler and loop eternally to keep thread alive."""

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
        redis_connection = create_redis_client(app_settings.CACHE_URI)
        while True:
            item = _get_scheduled_task_item_from_queue(redis_connection)
            if not item:
                continue

            workflow_scheduler_queue(item, scheduler_connection)


@app.command()
def show_schedule() -> None:
    """Show the currently configured schedule.

    in cli underscore is replaced by a dash `show-schedule`
    """
    for task in get_all_scheduler_tasks():
        typer.echo(f"[{task.id}] Next run: {task.next_run_time} | Trigger: {task.trigger}")


@app.command()
def force(task_id: str) -> None:
    """Force the execution of (a) scheduler(s) based on a task_id."""
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
def load_initial_schedule() -> None:
    """Load the initial schedule into the scheduler."""
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
        add_scheduled_task_to_queue(APSchedulerJobCreate(**schedule))  # type: ignore
