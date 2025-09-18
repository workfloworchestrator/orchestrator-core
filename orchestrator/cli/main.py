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

from orchestrator.cli import (
    database,
    generate,
    scheduler,
)
from orchestrator.llm_settings import llm_settings

app = typer.Typer()
app.add_typer(scheduler.app, name="scheduler", help="Access all the scheduler functions")
app.add_typer(database.app, name="db", help="Interact with the application database")
app.add_typer(generate.app, name="generate", help="Generate products, workflows and other artifacts")

if llm_settings.LLM_ENABLED:
    from orchestrator.cli import index_llm, resize_embedding, search_explore, speedtest

    app.add_typer(index_llm.app, name="index", help="(Re-)Index the search table.")
    app.add_typer(search_explore.app, name="search", help="Try out different search types.")
    app.add_typer(
        resize_embedding.app,
        name="embedding",
        help="Resize the vector dimension of the embedding column in the search table.",
    )
    app.add_typer(
        speedtest.app,
        name="speedtest",
        help="Search performance testing and analysis.",
    )


if __name__ == "__main__":
    app()
