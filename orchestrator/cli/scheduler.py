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
import typer
import time

from orchestrator.utils.redis_client import Redis

from orchestrator.schedules.service import (
    process_scheduler_queue, SCHEDULER_QUEUE
)
from orchestrator.schedules.scheduler import (
    get_all_scheduler_tasks,
    get_scheduler,
    get_scheduler_task,
)
from orchestrator.utils.redis_client import create_redis_client
from orchestrator.settings import app_settings

app: typer.Typer = typer.Typer()


@app.command()
def run() -> None:
    """Start scheduler and loop eternally to keep thread alive."""

    def _get_scheduled_task_item_from_queue(redis_conn: Redis) -> tuple[str, bytes] | None:
        """Get an item from the Redis Queue for scheduler tasks."""
        try:
            typer.echo(f"Getting scheduled task from queue: {redis_conn}")
            return redis_conn.brpop(SCHEDULER_QUEUE, timeout=1)
        except ConnectionError:
            typer.echo("Redis unavailable. Retrying in 3s...")
            time.sleep(3)
        except Exception as exc:
            typer.echo(f"Unexpected error: {exc}")
            time.sleep(1)

        return None

    typer.echo("Starting scheduler...")
    with get_scheduler() as scheduler_connection:
        reddis_connection = create_redis_client(app_settings.CACHE_URI)
        while True:
            typer.echo(f"Scheduler started at {scheduler_connection}")
            item = _get_scheduled_task_item_from_queue(reddis_connection)
            typer.echo(f"Scheduler started at {item}")
            if not item:
                continue

            process_scheduler_queue(item, scheduler_connection)



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
