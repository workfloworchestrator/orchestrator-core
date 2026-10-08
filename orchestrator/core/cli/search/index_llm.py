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
from orchestrator.core.search.indexing import (
    rebuild_search_paths,
    run_indexing_for_all_entities,
    run_indexing_for_entity,
)

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
    """Index the subscription search index.

    Args:
        subscription_id: UUID of a single subscription to index, `None` indexes all.
        dry_run: Make no database writes and no embedding calls.
        force_index: Re-index every field, ignoring the content hashes.
        show_progress: Show per-entity progress.

    CLI Options:
        ```shell
        Options:
            --subscription-id <str>               UUID (default = all)
            --dry-run / --no-dry-run              No DB writes  [default: no-dry-run]
            --force-index / --no-force-index      Force re-index (ignore hash cache)  [default: no-force-index]
            --show-progress / --no-show-progress  Show per-entity progress  [default: no-show-progress]
            --help                                Show this message and exit.
        ```
    """
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
    """Index the product search index.

    Args:
        product_id: UUID of a single product to index, `None` indexes all.
        dry_run: Make no database writes and no embedding calls.
        force_index: Re-index every field, ignoring the content hashes.
        show_progress: Show per-entity progress.

    CLI Options:
        ```shell
        Options:
            --product-id <str>                    UUID (default = all)
            --dry-run / --no-dry-run              No DB writes  [default: no-dry-run]
            --force-index / --no-force-index      Force re-index (ignore hash cache)  [default: no-force-index]
            --show-progress / --no-show-progress  Show per-entity progress  [default: no-show-progress]
            --help                                Show this message and exit.
        ```
    """
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
    """Index the process search index.

    Args:
        process_id: UUID of a single process to index, `None` indexes all.
        dry_run: Make no database writes and no embedding calls.
        force_index: Re-index every field, ignoring the content hashes.
        show_progress: Show per-entity progress.

    CLI Options:
        ```shell
        Options:
            --process-id <str>                    UUID (default = all)
            --dry-run / --no-dry-run              No DB writes  [default: no-dry-run]
            --force-index / --no-force-index      Force re-index (ignore hash cache)  [default: no-force-index]
            --show-progress / --no-show-progress  Show per-entity progress  [default: no-show-progress]
            --help                                Show this message and exit.
        ```
    """
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
    """Index the workflow search index.

    Args:
        workflow_id: UUID of a single workflow to index, `None` indexes all.
        dry_run: Make no database writes and no embedding calls.
        force_index: Re-index every field, ignoring the content hashes.
        show_progress: Show per-entity progress.

    CLI Options:
        ```shell
        Options:
            --workflow-id <str>                   UUID (default = all)
            --dry-run / --no-dry-run              No DB writes  [default: no-dry-run]
            --force-index / --no-force-index      Force re-index (ignore hash cache)  [default: no-force-index]
            --show-progress / --no-show-progress  Show per-entity progress  [default: no-show-progress]
            --help                                Show this message and exit.
        ```
    """
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
    """Index the product block search index.

    Args:
        product_block_id: UUID of a single product block to index, `None` indexes all.
        dry_run: Make no database writes and no embedding calls.
        force_index: Re-index every field, ignoring the content hashes.
        show_progress: Show per-entity progress.

    CLI Options:
        ```shell
        Options:
            --product-block-id <str>              UUID (default = all)
            --dry-run / --no-dry-run              No DB writes  [default: no-dry-run]
            --force-index / --no-force-index      Force re-index (ignore hash cache)  [default: no-force-index]
            --show-progress / --no-show-progress  Show per-entity progress  [default: no-show-progress]
            --help                                Show this message and exit.
        ```
    """
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
    """Index the resource type search index.

    Args:
        resource_type_id: UUID of a single resource type to index, `None` indexes all.
        dry_run: Make no database writes and no embedding calls.
        force_index: Re-index every field, ignoring the content hashes.
        show_progress: Show per-entity progress.

    CLI Options:
        ```shell
        Options:
            --resource-type-id <str>              UUID (default = all)
            --dry-run / --no-dry-run              No DB writes  [default: no-dry-run]
            --force-index / --no-force-index      Force re-index (ignore hash cache)  [default: no-force-index]
            --show-progress / --no-show-progress  Show per-entity progress  [default: no-show-progress]
            --help                                Show this message and exit.
        ```
    """
    run_indexing_for_entity(
        entity_kind=EntityType.RESOURCE_TYPE,
        entity_id=resource_type_id,
        dry_run=dry_run,
        force_index=force_index,
        show_progress=show_progress,
    )


@app.command("all")
def all_command(force_index: ForceIndex = False) -> None:
    """Index all entity types and rebuild the ai_search_paths table.

    Args:
        force_index: Re-index every field, ignoring the content hashes.

    CLI Options:
        ```shell
        Options:
            --force-index / --no-force-index  Force re-index (ignore hash cache)  [default: no-force-index]
            --help                            Show this message and exit.
        ```
    """
    run_indexing_for_all_entities(force_index=force_index)


@app.command("rebuild-paths")
def rebuild_paths_command() -> None:
    """Recompute the ai_search_paths distinct-paths table from ai_search_index.

    CLI Options:
        ```shell
        Options:
            --help  Show this message and exit.
        ```
    """
    rebuild_search_paths()


if __name__ == "__main__":
    app()
