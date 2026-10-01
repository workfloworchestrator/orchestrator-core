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

from typing import Annotated

import typer

from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.indexing import rebuild_search_paths, run_indexing_for_entity

app = typer.Typer(
    name="index",
    help="Index search indexes",
)

EntityId = Annotated[str | None, typer.Option(help="UUID (default = all)")]
DryRun = Annotated[bool, typer.Option(help="No DB writes")]
ForceIndex = Annotated[bool, typer.Option(help="Force re-index (ignore hash cache)")]
ShowProgress = Annotated[bool, typer.Option(help="Show per-entity progress")]


@app.command("subscriptions")
def subscriptions_command(
    subscription_id: EntityId = None,
    dry_run: DryRun = False,
    force_index: ForceIndex = False,
    show_progress: ShowProgress = False,
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
    product_id: EntityId = None,
    dry_run: DryRun = False,
    force_index: ForceIndex = False,
    show_progress: ShowProgress = False,
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
    process_id: EntityId = None,
    dry_run: DryRun = False,
    force_index: ForceIndex = False,
    show_progress: ShowProgress = False,
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
    workflow_id: EntityId = None,
    dry_run: DryRun = False,
    force_index: ForceIndex = False,
    show_progress: ShowProgress = False,
) -> None:
    """Index workflow_search_index."""
    run_indexing_for_entity(
        entity_kind=EntityType.WORKFLOW,
        entity_id=workflow_id,
        dry_run=dry_run,
        force_index=force_index,
        show_progress=show_progress,
    )


@app.command("product-blocks")
def product_blocks_command(
    product_block_id: EntityId = None,
    dry_run: DryRun = False,
    force_index: ForceIndex = False,
    show_progress: ShowProgress = False,
) -> None:
    """Index product_block_search_index."""
    run_indexing_for_entity(
        entity_kind=EntityType.PRODUCT_BLOCK,
        entity_id=product_block_id,
        dry_run=dry_run,
        force_index=force_index,
        show_progress=show_progress,
    )


@app.command("resource-types")
def resource_types_command(
    resource_type_id: EntityId = None,
    dry_run: DryRun = False,
    force_index: ForceIndex = False,
    show_progress: ShowProgress = False,
) -> None:
    """Index resource_type_search_index."""
    run_indexing_for_entity(
        entity_kind=EntityType.RESOURCE_TYPE,
        entity_id=resource_type_id,
        dry_run=dry_run,
        force_index=force_index,
        show_progress=show_progress,
    )


@app.command("rebuild-paths")
def rebuild_paths_command() -> None:
    """Recompute the ai_search_paths distinct-paths table from ai_search_index."""
    rebuild_search_paths()


if __name__ == "__main__":
    app()
