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
from time import sleep

import schedule
import typer

from orchestrator.schedules import ALL_SCHEDULERS

log = logging.getLogger(__name__)

app: typer.Typer = typer.Typer()


@app.command()
def run() -> None:
    """Loop eternally and run schedulers at configured times."""
    for s in ALL_SCHEDULERS:
        job = getattr(schedule.every(s.period), s.time_unit)
        if s.at:
            job = job.at(s.at)
        job.do(s).tag(s.name)
    log.info("Starting Schedule")
    for j in schedule.jobs:
        log.info("%s: %s", ", ".join(j.tags), j)
    while True:
        schedule.run_pending()
        idle = schedule.idle_seconds()
        if idle < 0:
            log.info("Next job in queue is scheduled in the past, run it now.")
        else:
            log.info("Sleeping for %d seconds", idle)
            sleep(idle)


@app.command()
def show_schedule() -> None:
    """Show the currently configured schedule."""
    for s in ALL_SCHEDULERS:
        at_str = f"@ {s.at} " if s.at else ""
        typer.echo(f"{s.name}: {s.__name__} {at_str}every {s.period} {s.time_unit}")


@app.command()
def force(keyword: str) -> None:
    """Force the execution of (a) scheduler(s) based on a keyword."""
    for s in ALL_SCHEDULERS:
        if keyword in s.name or keyword in s.__name__:
            s()
