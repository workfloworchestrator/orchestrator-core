import typer

from orchestrator.search.core.types import EntityType
from orchestrator.search.indexing import run_indexing_for_entity

app = typer.Typer(
    name="index",
    help="Index search indexes",
)


@app.command("subscriptions")
def subscriptions_command(
    subscription_id: str | None = typer.Option(None, help="UUID (default = all)"),
    dry_run: bool = typer.Option(False, help="No DB writes"),
    force_index: bool = typer.Option(False, help="Force re-index (ignore hash cache)"),
) -> None:
    """Index subscription_search_index."""
    run_indexing_for_entity(
        entity_kind=EntityType.SUBSCRIPTION,
        entity_id=subscription_id,
        dry_run=dry_run,
        force_index=force_index,
    )


@app.command("products")
def products_command(
    product_id: str | None = typer.Option(None, help="UUID (default = all)"),
    dry_run: bool = typer.Option(False, help="No DB writes"),
    force_index: bool = typer.Option(False, help="Force re-index (ignore hash cache)"),
) -> None:
    """Index product_search_index."""
    run_indexing_for_entity(
        entity_kind=EntityType.PRODUCT,
        entity_id=product_id,
        dry_run=dry_run,
        force_index=force_index,
    )


@app.command("processes")
def processes_command(
    process_id: str | None = typer.Option(None, help="UUID (default = all)"),
    dry_run: bool = typer.Option(False, help="No DB writes"),
    force_index: bool = typer.Option(False, help="Force re-index (ignore hash cache)"),
) -> None:
    """Index process_search_index."""
    run_indexing_for_entity(
        entity_kind=EntityType.PROCESS,
        entity_id=process_id,
        dry_run=dry_run,
        force_index=force_index,
    )


@app.command("workflows")
def workflows_command(
    workflow_id: str | None = typer.Option(None, help="UUID (default = all)"),
    dry_run: bool = typer.Option(False, help="No DB writes"),
    force_index: bool = typer.Option(False, help="Force re-index (ignore hash cache)"),
) -> None:
    """Index workflow_search_index."""
    run_indexing_for_entity(
        entity_kind=EntityType.WORKFLOW,
        entity_id=workflow_id,
        dry_run=dry_run,
        force_index=force_index,
    )


if __name__ == "__main__":
    app()
