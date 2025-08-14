from typing import Optional

import typer

from orchestrator.search.indexing.tasks import index_processes, index_products, index_subscriptions, index_workflows

app = typer.Typer(
    name="index",
    help="Index search indexes",
)


@app.command("subscriptions")
def subscriptions_command(
    subscription_id: Optional[str] = typer.Option(None, help="UUID (default = all)"),
    dry_run: bool = typer.Option(False, help="No DB writes"),
    force_index: bool = typer.Option(False, help="Force re-index (ignore hash cache)"),
) -> None:
    """Index subscription_search_index."""
    index_subscriptions(subscription_id=subscription_id, dry_run=dry_run, force_index=force_index)


@app.command("products")
def products_command(
    product_id: Optional[str] = typer.Option(None, help="UUID (default = all)"),
    dry_run: bool = typer.Option(False, help="No DB writes"),
    force_index: bool = typer.Option(False, help="Force re-index (ignore hash cache)"),
) -> None:
    """Index product_search_index."""
    index_products(product_id=product_id, dry_run=dry_run, force_index=force_index)


@app.command("processes")
def processes_command(
    process_id: Optional[str] = typer.Option(None, help="UUID (default = all)"),
    dry_run: bool = typer.Option(False, help="No DB writes"),
    force_index: bool = typer.Option(False, help="Force re-index (ignore hash cache)"),
) -> None:
    """Index process_search_index."""
    index_processes(process_id=process_id, dry_run=dry_run, force_index=force_index)


@app.command("workflows")
def workflows_command(
    workflow_id: Optional[str] = typer.Option(None, help="UUID (default = all)"),
    dry_run: bool = typer.Option(False, help="No DB writes"),
    force_index: bool = typer.Option(False, help="Force re-index (ignore hash cache)"),
) -> None:
    """Index workflow_search_index."""
    index_workflows(workflow_id=workflow_id, dry_run=dry_run, force_index=force_index)


if __name__ == "__main__":
    app()
