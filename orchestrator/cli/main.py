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
from json import loads
from typing import List, Optional

import typer

from orchestrator.cli import database, scheduler

app = typer.Typer()
app.add_typer(scheduler.app, name="scheduler", help="Access all the scheduler functions")


@app.command(name="db")
def db(
    command: str = typer.Argument(..., help="Alembic sub commands"),
    arguments: Optional[List[str]] = typer.Argument(None, help="Comma separated string of arguments"),
    options: Optional[str] = typer.Option({}, help="Alembic options as json string"),
) -> None:
    if command == "init":
        return database.init()
    else:
        kw_args = {}
        if options:
            kw_args = loads(options).to_dict()
        return database.alebic_proxy(command, *arguments, **kw_args)  # type: ignore


if __name__ == "__main__":
    app()
