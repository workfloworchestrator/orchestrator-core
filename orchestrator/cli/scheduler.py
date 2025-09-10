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


import logging
import time

import typer

from orchestrator.schedules.scheduler import (
    get_paused_scheduler,
)

log = logging.getLogger(__name__)

app: typer.Typer = typer.Typer()


@app.command()
def run() -> None:
    """Start scheduler and loop eternally to keep thread alive."""
    with get_paused_scheduler() as scheduler:
        scheduler.resume()

        while True:
            time.sleep(1)


@app.command()
def show_schedule() -> None:
    """Show the currently configured schedule.

    in cli underscore is replaced by a dash `show-schedule`
    """
    with get_paused_scheduler() as scheduler:
        jobs = scheduler.get_jobs()

    for job in jobs:
        typer.echo(f"[{job.id}] Next run: {job.next_run_time} | Trigger: {job.trigger}")


@app.command()
def force(job_id: str) -> None:
    """Force the execution of (a) scheduler(s) based on a job_id."""
    with get_paused_scheduler() as scheduler:
        job = scheduler.get_job(job_id)

    if not job:
        typer.echo(f"Job '{job_id}' not found.")
        raise typer.Exit(code=1)

    typer.echo(f"Running job [{job.id}] now...")
    try:
        job.func(*job.args or (), **job.kwargs or {})
        typer.echo("Job executed successfully.")
    except Exception as e:
        typer.echo(f"Job execution failed: {e}")
        raise typer.Exit(code=1)
