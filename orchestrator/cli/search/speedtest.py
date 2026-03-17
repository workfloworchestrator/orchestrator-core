import asyncio
import time
from typing import Any

import structlog
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from orchestrator.db import db
from orchestrator.search.core.embedding import QueryEmbedder
from orchestrator.search.core.types import EntityType
from orchestrator.search.core.validators import is_uuid
from orchestrator.search.query import engine
from orchestrator.search.query.queries import SelectQuery

logger = structlog.get_logger(__name__)
console = Console()

app = typer.Typer(name="speedtest", help="Search speed testing")

DEFAULT_QUERIES = [
    "network",
    "fiber",
    "port",
    "network infrastructure",
    "fiber connection",
    "internet service",
    "subscription",
    "active",
    "configuration",
    "service provider",
]


async def generate_embeddings_for_queries(queries: list[str]) -> dict[str, list[float]]:
    embedding_lookup = {}

    for query in queries:
        try:
            embedding = await QueryEmbedder.generate_for_text_async(query)
            if embedding:
                embedding_lookup[query] = embedding
            else:
                logger.warning("Failed to generate embedding for query", query=query)
        except Exception as e:
            logger.error("Error generating embedding", query=query, error=str(e))

    return embedding_lookup


async def run_single_query(query_text: str, embedding_lookup: dict[str, list[float]]) -> dict[str, Any]:
    query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=query_text, limit=30)

    query_embedding = None

    if is_uuid(query_text):
        logger.debug("Using fuzzy-only ranking for full UUID", query_text=query_text)
    else:
        query_embedding = embedding_lookup[query_text]

    with db.session as session:
        start_time = time.perf_counter()
        response = await engine.execute_search(
            query=query, db_session=session, cursor=None, query_embedding=query_embedding
        )
        end_time = time.perf_counter()

        return {
            "query": query_text,
            "time": end_time - start_time,
            "results": len(response.results),
            "search_type": response.metadata.search_type if hasattr(response, "metadata") else "unknown",
        }


@app.command()
def quick(
    queries: list[str] | None = typer.Option(None, "--query", "-q", help="Custom queries to test"),
) -> None:
    test_queries = queries if queries else DEFAULT_QUERIES

    console.print(f"[bold blue]Quick Speed Test[/bold blue] - Testing {len(test_queries)} queries")

    async def run_tests() -> list[dict[str, Any]]:
        embedding_lookup = await generate_embeddings_for_queries(test_queries)

        results = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Running queries...", total=len(test_queries))

            for query in test_queries:
                result = await run_single_query(query, embedding_lookup)
                results.append(result)
                progress.advance(task)

        return results

    results = asyncio.run(run_tests())

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Query", style="dim", width=25)
    table.add_column("Time", justify="right", style="cyan")
    table.add_column("Type", justify="center", style="yellow")
    table.add_column("Results", justify="right", style="green")

    total_time = 0

    for result in results:
        time_ms = result["time"] * 1000
        total_time += result["time"]

        table.add_row(
            result["query"][:24] + "..." if len(result["query"]) > 24 else result["query"],
            f"{time_ms:.1f}ms",
            result["search_type"],
            str(result["results"]),
        )

    console.print(table)
    console.print()

    avg_time = total_time / len(results) * 1000
    max_time = max(r["time"] for r in results) * 1000

    console.print("[bold]Summary:[/bold]")
    console.print(f"  Total time: {total_time * 1000:.1f}ms")
    console.print(f"  Average: {avg_time:.1f}ms")
    console.print(f"  Slowest: {max_time:.1f}ms")

    by_type: dict[str, list[float]] = {}
    for result in results:
        search_type = result["search_type"]
        if search_type not in by_type:
            by_type[search_type] = []
        by_type[search_type].append(result["time"] * 1000)

    for search_type, times in by_type.items():
        avg = sum(times) / len(times)
        console.print(f"  {search_type.capitalize()}: {avg:.1f}ms avg ({len(times)} queries)")


if __name__ == "__main__":
    app()
