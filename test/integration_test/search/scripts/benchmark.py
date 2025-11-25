# Copyright 2019-2025 SURF, GÉANT.
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


from collections import defaultdict
from dataclasses import dataclass
from time import perf_counter

import structlog
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from orchestrator.db import db
from orchestrator.llm_settings import llm_settings
from orchestrator.search.core.types import EntityType
from orchestrator.search.query import engine
from orchestrator.search.query.queries import SelectQuery

from ..fixtures import TEST_SUBSCRIPTIONS
from ..helpers import BenchmarkQuery, ModelConfig, load_benchmark_queries, load_model_configs

logger = structlog.get_logger(__name__)
console = Console()


@dataclass
class BenchmarkResult:
    """Results from benchmarking a single query with a model."""

    query_text: str
    model_name: str
    latency_ms: float
    result_count: int
    top_results: list[str]
    scores: list[float]
    search_type: str
    rank_correlation: float | None = None
    top_k_overlap: dict[int, float] | None = None
    expected_ranking: list[str] | None = None


def calculate_spearman_correlation(predicted: list[str], expected: list[str]) -> float:
    """Calculate Spearman's rank correlation coefficient.

    Returns value between -1 and 1 (1.0 = identical rankings, 0.0 = no correlation).
    """
    if not expected or not predicted:
        return 0.0

    common_items = set(predicted) & set(expected)
    if len(common_items) < 2:
        return 0.0

    predicted_ranks = {item: rank for rank, item in enumerate(predicted) if item in common_items}
    expected_ranks = {item: rank for rank, item in enumerate(expected) if item in common_items}

    n = len(common_items)
    sum_d_squared = sum((predicted_ranks[item] - expected_ranks[item]) ** 2 for item in common_items)

    if n <= 1:
        return 0.0

    return 1.0 - (6.0 * sum_d_squared) / (n * (n * n - 1))


def calculate_top_k_overlap(predicted: list[str], expected: list[str], k_values: list[int]) -> dict[int, float]:
    """Calculate what fraction of top-K results appear in ground truth top-K."""
    results = {}

    for k in k_values:
        predicted_top_k = set(predicted[:k])
        expected_top_k = set(expected[:k])

        if not expected_top_k:
            results[k] = 0.0
            continue

        overlap = len(predicted_top_k & expected_top_k)
        results[k] = overlap / min(k, len(expected_top_k))

    return results


async def reindex_with_model(model_config: ModelConfig) -> None:
    """Re-index all entities using the specified model's embeddings."""
    console.print(f"Re-indexing with {model_config.name}...")

    from sqlalchemy import text

    from orchestrator.db import SubscriptionTable
    from orchestrator.search.core.embedding import EmbeddingIndexer

    from ..helpers import index_subscription

    # Generate embeddings for all test subscriptions
    descriptions = [sub["description"] for sub in TEST_SUBSCRIPTIONS]

    embeddings = EmbeddingIndexer.get_embeddings_from_api_batch(descriptions, dry_run=False)

    embedding_map = {}
    for sub_data, embedding in zip(TEST_SUBSCRIPTIONS, embeddings):
        embedding_map[str(sub_data["subscription_id"])] = embedding

    # Clear and re-index
    with db.session as session:
        session.execute(text("TRUNCATE TABLE ai_search_index CASCADE"))
        session.commit()

        subscriptions = session.query(SubscriptionTable).all()
        for subscription in subscriptions:
            sub_id = str(subscription.subscription_id)
            if sub_id in embedding_map:
                index_subscription(subscription, embedding_map[sub_id], session)

        session.commit()

    console.print(f"✓ Re-indexed {len(embedding_map)} entities with {model_config.name}")


async def run_benchmark_query(
    query: BenchmarkQuery, model_config: ModelConfig, embedding_cache: dict[str, list[float]]
) -> BenchmarkResult:
    """Run a benchmark query with the specified model.

    Note: Assumes llm_settings.EMBEDDING_MODEL is already set to model_config.model
    by the caller (reindex_with_model sets it for the entire model test run).
    """
    from orchestrator.search.core.embedding import EmbeddingIndexer

    cache_key = f"{model_config.model}:{query.query_text.lower()}"
    if cache_key in embedding_cache:
        query_embedding = embedding_cache[cache_key]
    else:
        embeddings = EmbeddingIndexer.get_embeddings_from_api_batch([query.query_text], dry_run=False)
        query_embedding = embeddings[0]
        embedding_cache[cache_key] = query_embedding

    search_query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=query.query_text, limit=10)

    with db.session as session:
        start_time = perf_counter()
        response = await engine.execute_search(
            query=search_query, db_session=session, cursor=None, query_embedding=query_embedding
        )
        end_time = perf_counter()

    result_ids = [str(r.entity_id) for r in response.results]
    scores = [float(r.score) for r in response.results]

    rank_correlation = None
    top_k_overlap = None

    if query.expected_ranking:
        rank_correlation = calculate_spearman_correlation(result_ids, query.expected_ranking)
        top_k_overlap = calculate_top_k_overlap(result_ids, query.expected_ranking, [5])

    return BenchmarkResult(
        query_text=query.query_text,
        model_name=model_config.name,
        latency_ms=(end_time - start_time) * 1000,
        result_count=len(result_ids),
        top_results=result_ids,
        scores=scores,
        search_type=response.metadata.search_type,
        rank_correlation=rank_correlation,
        top_k_overlap=top_k_overlap,
        expected_ranking=query.expected_ranking,
    )


async def compare_models() -> None:
    """Compare multiple embedding models on search ranking quality.

    This function runs a suite of benchmark queries using different embedding models
    and compares their ranking quality and performance.
    """
    console.print("[bold blue]Embedding Model Benchmark[/bold blue]\n")

    # Load configurations
    queries = load_benchmark_queries()
    models = load_model_configs()

    console.print(f"Loaded {len(queries)} benchmark queries")
    console.print(f"Loaded {len(models)} model configurations\n")

    results = []
    embedding_cache: dict[str, list[float]] = {}

    original_model = llm_settings.EMBEDDING_MODEL

    try:
        for model in models:
            console.print(f"\n[bold]Testing model: {model.name}[/bold]")

            # Set the embedding model for this model test
            llm_settings.EMBEDDING_MODEL = model.model

            # Re-index all entities with this model's embeddings
            await reindex_with_model(model)

            # Run all queries with this model
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"Running {len(queries)} queries...", total=len(queries))

                for query in queries:
                    progress.update(task, description=f"Query: {query.query_text[:40]}...")
                    result = await run_benchmark_query(query, model, embedding_cache)
                    results.append(result)
                    progress.advance(task)

            console.print(f"✓ Completed {model.name}\n")
    finally:
        # Restore original settings
        llm_settings.EMBEDDING_MODEL = original_model

    display_benchmark_results(results, queries, models)


def display_ranking_comparison(query_results: list[BenchmarkResult], expected_ranking: list[str]) -> None:
    """Display side-by-side ranking comparison with visual indicators (✓/⚠/✗)."""
    if not expected_ranking:
        return

    # Build mapping from subscription_id to description (truncated to 50 chars)
    id_to_desc = {
        str(sub["subscription_id"]): (
            sub["description"][:47] + "..." if len(sub["description"]) > 50 else sub["description"]
        )
        for sub in TEST_SUBSCRIPTIONS
    }

    # Create comparison table
    comparison_table = Table(show_header=True, header_style="bold magenta", box=None)
    comparison_table.add_column("Rank", justify="center", style="dim", width=5)
    comparison_table.add_column("Ground Truth", style="white", width=55)

    for result in query_results:
        comparison_table.add_column(result.model_name, style="cyan", width=55)

    max_rank = min(5, len(expected_ranking))
    for rank in range(max_rank):
        expected_id = expected_ranking[rank] if rank < len(expected_ranking) else None
        expected_desc = id_to_desc.get(expected_id, expected_id) if expected_id else "—"
        row = [f"{rank + 1}", expected_desc]

        for result in query_results:
            if rank < len(result.top_results):
                predicted_id = result.top_results[rank]
                predicted_desc = id_to_desc.get(predicted_id, predicted_id)

                if predicted_id in expected_ranking:
                    expected_pos = expected_ranking.index(predicted_id)
                    if expected_pos == rank:
                        row.append(f"✓ {predicted_desc}")
                    else:
                        row.append(f"⚠ {predicted_desc} (exp: #{expected_pos + 1})")
                else:
                    row.append(f"✗ {predicted_desc}")
            else:
                row.append("—")

        comparison_table.add_row(*row)

    console.print(comparison_table)


def display_benchmark_results(
    results: list[BenchmarkResult], queries: list[BenchmarkQuery], models: list[ModelConfig]
) -> None:
    """Display benchmark results with simple metrics and visual comparisons."""

    # Group results by model
    results_by_model: dict[str, list[BenchmarkResult]] = defaultdict(list)
    for result in results:
        results_by_model[result.model_name].append(result)

    console.print("\n[bold]Summary by Model[/bold]\n")
    summary_table = Table(show_header=True, header_style="bold magenta")
    summary_table.add_column("Model", style="cyan")
    summary_table.add_column("Avg Latency", justify="right", style="yellow")
    summary_table.add_column("Avg Rank Corr", justify="right", style="green")
    summary_table.add_column("Avg Top-5 Overlap", justify="right", style="green")

    for model_name, model_results in results_by_model.items():
        avg_latency = sum(r.latency_ms for r in model_results) / len(model_results)

        corr_values = [r.rank_correlation for r in model_results if r.rank_correlation is not None]
        top5_values = [r.top_k_overlap[5] for r in model_results if r.top_k_overlap and 5 in r.top_k_overlap]

        if corr_values:
            avg_corr = sum(corr_values) / len(corr_values)
            avg_top5 = sum(top5_values) / len(top5_values) if top5_values else 0.0
            summary_table.add_row(model_name, f"{avg_latency:.1f}ms", f"{avg_corr:.3f}", f"{avg_top5:.1%}")
        else:
            summary_table.add_row(model_name, f"{avg_latency:.1f}ms", "N/A", "N/A")

    console.print(summary_table)

    # Always show detailed per-query results
    for query in queries:
        console.print(f"\n[bold]Query: {query.query_text}[/bold]")
        console.print(f"[dim]{query.description}[/dim]\n")

        detail_table = Table(show_header=True, header_style="bold magenta")
        detail_table.add_column("Model", style="cyan")
        detail_table.add_column("Latency", justify="right", style="yellow")
        detail_table.add_column("Rank Corr (ρ)", justify="right", style="green")
        detail_table.add_column("Top-5 Overlap", justify="right", style="green")

        query_results = [r for r in results if r.query_text == query.query_text]
        for result in query_results:
            if result.rank_correlation is not None and result.top_k_overlap is not None:
                top5 = result.top_k_overlap.get(5, 0.0)
                detail_table.add_row(
                    result.model_name,
                    f"{result.latency_ms:.1f}ms",
                    f"{result.rank_correlation:.3f}",
                    f"{top5:.1%}",
                )
            else:
                detail_table.add_row(result.model_name, f"{result.latency_ms:.1f}ms", "N/A", "N/A")

        console.print(detail_table)

        if query.expected_ranking:
            console.print("\n[bold]Ranking Comparison (Top 5)[/bold]")
            display_ranking_comparison(query_results, query.expected_ranking)
