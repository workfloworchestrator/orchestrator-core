"""Run benchmark for a single embedding model in isolated environment.

This module is designed to run in a fresh Python process (subprocess)
to avoid SQLAlchemy Vector dimension caching issues. It benchmarks ONE model and outputs
results as JSON.
"""

import asyncio
import json
import os
from time import perf_counter

from rich.console import Console


async def reindex_with_model(model_config, target_dimension: int, console) -> None:
    """Re-index all entities using the specified model's embeddings.

    Note: This function is called from within an isolated subprocess where
    EMBEDDING_DIMENSION is already set correctly before any imports, so we can
    safely use the ORM without dimension caching issues.

    Args:
        model_config: Model configuration
        target_dimension: Target embedding dimension (already capped at 2000)
        console: Rich console for output
    """
    from sqlalchemy import text

    from orchestrator.cli.search.resize_embedding import alter_embedding_column_dimension
    from orchestrator.db import SubscriptionTable, db
    from orchestrator.search.core.embedding import EmbeddingIndexer
    from test.integration_tests.search.fixtures import TEST_SUBSCRIPTIONS
    from test.integration_tests.search.helpers import index_subscription

    console.print(f"Re-indexing with {model_config.name}...")

    # Truncate existing data and resize columns
    console.print(f"Resizing embedding column to {target_dimension} dimensions...")
    with db.session as session:
        session.execute(text("TRUNCATE TABLE ai_search_index CASCADE"))
        session.execute(text("TRUNCATE TABLE search_queries CASCADE"))
        session.commit()

    alter_embedding_column_dimension(target_dimension)
    console.print(f"Resized to {target_dimension} dimensions")

    # Generate embeddings for all test subscriptions
    descriptions = [str(sub["description"]) for sub in TEST_SUBSCRIPTIONS]
    embeddings = EmbeddingIndexer.get_embeddings_from_api_batch(descriptions, dry_run=False)

    embedding_map = {}
    for sub_data, embedding in zip(TEST_SUBSCRIPTIONS, embeddings):
        embedding_map[str(sub_data["subscription_id"])] = embedding

    with db.session as session:
        subscriptions = session.query(SubscriptionTable).all()
        for subscription in subscriptions:
            sub_id = str(subscription.subscription_id)
            if sub_id in embedding_map:
                index_subscription(subscription, embedding_map[sub_id], session)

        session.commit()

    console.print(f"Re-indexed {len(embedding_map)} entities with {model_config.name}")


async def benchmark_single_model(
    model_name: str,
    model_id: str,
    dimension: int,
    output_file: str,
    database_uri: str,
) -> None:
    """Benchmark a single embedding model in isolated process.

    Args:
        model_name: Display name for the model (e.g., "OpenAI Large")
        model_id: LiteLLM model identifier (e.g., "openai/text-embedding-3-large")
        dimension: Native embedding dimension
        output_file: Path to write JSON results
        database_uri: Database connection string
    """
    target_dimension = min(dimension, 2000)

    # CRITICAL: Set dimension BEFORE any orchestrator imports
    # This ensures Vector columns in SQLAlchemy models are created with correct dimensions
    os.environ["EMBEDDING_DIMENSION"] = str(target_dimension)

    # Now safe to import orchestrator modules - they'll use correct dimension
    from orchestrator.db import db
    from orchestrator.db.database import Database
    from orchestrator.llm_settings import llm_settings
    from orchestrator.search.core.embedding import EmbeddingIndexer
    from orchestrator.search.core.types import EntityType
    from orchestrator.search.query import engine
    from orchestrator.search.query.queries import SelectQuery
    from test.integration_tests.search.helpers import ModelConfig, load_benchmark_queries
    from test.integration_tests.search.scripts.benchmark.benchmark import BenchmarkResult
    from test.integration_tests.search.scripts.benchmark.metrics import (
        calculate_spearman_correlation,
        calculate_top_k_overlap,
    )

    db.update(Database(database_uri))  # type: ignore[attr-defined]

    llm_settings.EMBEDDING_MODEL = model_id
    llm_settings.EMBEDDING_DIMENSION = target_dimension

    console = Console()
    console.print(f"Benchmarking {model_name} with dimension {target_dimension}")

    model = ModelConfig(name=model_name, model=model_id, dimension=dimension)

    # Re-index with this model
    await reindex_with_model(model, target_dimension, console)

    queries = load_benchmark_queries()

    results = []

    for query in queries:
        # Generate query embedding
        query_embedding = EmbeddingIndexer.get_embeddings_from_api_batch([query.query_text], dry_run=False)[0]

        # Execute search
        with db.session as session:
            start_time = perf_counter()
            response = await engine.execute_search(
                query=SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=query.query_text, limit=10),
                db_session=session,
                cursor=None,
                query_embedding=query_embedding,
            )
            end_time = perf_counter()

        # Extract results and calculate metrics
        result_ids = [str(r.entity_id) for r in response.results]
        rank_correlation = (
            calculate_spearman_correlation(result_ids, query.expected_ranking) if query.expected_ranking else None
        )
        top_k_overlap = (
            calculate_top_k_overlap(result_ids, query.expected_ranking, [5]) if query.expected_ranking else None
        )

        results.append(
            BenchmarkResult(
                query_text=query.query_text,
                model_name=model_name,
                latency_ms=(end_time - start_time) * 1000,
                result_count=len(result_ids),
                top_results=result_ids,
                scores=[float(r.score) for r in response.results],
                search_type=response.metadata.search_type,
                rank_correlation=rank_correlation,
                top_k_overlap=top_k_overlap,
                expected_ranking=query.expected_ranking,
            )
        )

        console.print(f"  Completed query: {query.query_text[:40]}...")

    # Output results as JSON to file
    results_data = [r.to_dict() for r in results]
    with open(output_file, "w") as f:
        json.dump(results_data, f, indent=2)

    console.print(f"Completed benchmark for {model_name} - wrote {len(results)} results")


if __name__ == "__main__":
    """Entry point when run as subprocess.

    Reads arguments from environment variables:
    - MODEL_NAME: Display name
    - MODEL_ID: LiteLLM identifier
    - DIMENSION: Native dimension
    - OUTPUT_FILE: JSON output path
    - DATABASE_URI: Database connection
    """
    model_name = os.environ["MODEL_NAME"]
    model_id = os.environ["MODEL_ID"]
    dimension = int(os.environ["DIMENSION"])
    output_file = os.environ["OUTPUT_FILE"]
    database_uri = os.environ["DATABASE_URI"]

    asyncio.run(
        benchmark_single_model(
            model_name=model_name,
            model_id=model_id,
            dimension=dimension,
            output_file=output_file,
            database_uri=database_uri,
        )
    )
