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

import typer

from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.indexing import run_indexing_for_entity

app = typer.Typer(
    name="index",
    help="Index search indexes",
)


@app.command("subscriptions")
def subscriptions_command(
    subscription_id: str | None = typer.Option(None, help="UUID (default = all)"),
    dry_run: bool = typer.Option(False, help="No DB writes"),
    force_index: bool = typer.Option(False, help="Force re-index (ignore hash cache)"),
    show_progress: bool = typer.Option(False, help="Show per-entity progress"),
) -> None:
    """Index subscription_search_index."""
    run_indexing_for_entity(
        entity_kind=EntityType.SUBSCRIPTION,
        entity_id=subscription_id,
        dry_run=dry_run,
        force_index=force_index,
        show_progress=show_progress,
    )


@app.command("products")
def products_command(
    product_id: str | None = typer.Option(None, help="UUID (default = all)"),
    dry_run: bool = typer.Option(False, help="No DB writes"),
    force_index: bool = typer.Option(False, help="Force re-index (ignore hash cache)"),
    show_progress: bool = typer.Option(False, help="Show per-entity progress"),
) -> None:
    """Index product_search_index."""
    run_indexing_for_entity(
        entity_kind=EntityType.PRODUCT,
        entity_id=product_id,
        dry_run=dry_run,
        force_index=force_index,
        show_progress=show_progress,
    )


@app.command("processes")
def processes_command(
    process_id: str | None = typer.Option(None, help="UUID (default = all)"),
    dry_run: bool = typer.Option(False, help="No DB writes"),
    force_index: bool = typer.Option(False, help="Force re-index (ignore hash cache)"),
    show_progress: bool = typer.Option(False, help="Show per-entity progress"),
) -> None:
    """Index process_search_index."""
    run_indexing_for_entity(
        entity_kind=EntityType.PROCESS,
        entity_id=process_id,
        dry_run=dry_run,
        force_index=force_index,
        show_progress=show_progress,
    )


@app.command("workflows")
def workflows_command(
    workflow_id: str | None = typer.Option(None, help="UUID (default = all)"),
    dry_run: bool = typer.Option(False, help="No DB writes"),
    force_index: bool = typer.Option(False, help="Force re-index (ignore hash cache)"),
    show_progress: bool = typer.Option(False, help="Show per-entity progress"),
) -> None:
    """Index workflow_search_index."""
    run_indexing_for_entity(
        entity_kind=EntityType.WORKFLOW,
        entity_id=workflow_id,
        dry_run=dry_run,
        force_index=force_index,
        show_progress=show_progress,
    )


if __name__ == "__main__":
    app()
