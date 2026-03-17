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


from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from orchestrator.db import ProductTable, SubscriptionTable, db
from orchestrator.llm_settings import llm_settings
from orchestrator.search.core.embedding import EmbeddingIndexer
from orchestrator.search.core.types import EntityType
from orchestrator.search.query import engine
from orchestrator.search.query.queries import SelectQuery

from ..fixtures import GROUND_TRUTH_QUERIES, TEST_PRODUCT, TEST_SUBSCRIPTIONS
from ..helpers import GROUND_TRUTH_FILE, index_subscription, save_ground_truth

console = Console()


async def generate_entity_embeddings() -> dict[str, list[float]]:
    """Generate embeddings for all test entities."""
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), TimeElapsedColumn(), console=console
    ) as progress:
        progress.add_task(f"Generating embeddings for {len(TEST_SUBSCRIPTIONS)} entities...", total=None)

        descriptions = [str(sub["description"]) for sub in TEST_SUBSCRIPTIONS]
        embeddings_list = EmbeddingIndexer.get_embeddings_from_api_batch(descriptions, dry_run=False)

        # Map descriptions to embeddings
        embeddings = {desc.lower(): emb for desc, emb in zip(descriptions, embeddings_list)}

    console.print(f"[green]✓[/green] Generated {len(embeddings)} entity embeddings")
    return embeddings


async def record_ground_truth_queries(embeddings_cache: dict[str, list[float]]) -> list[dict]:
    """Run all ground truth queries and record result rankings."""
    queries = []

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), TimeElapsedColumn(), console=console
    ) as progress:
        progress.add_task(f"Recording {len(GROUND_TRUTH_QUERIES)} ground truth queries...", total=None)

        for query_data in GROUND_TRUTH_QUERIES:
            query_text = query_data["query_text"]
            cache_key = query_text.lower()

            # Generate query embedding if not cached
            if cache_key not in embeddings_cache:
                query_embedding = EmbeddingIndexer.get_embeddings_from_api_batch([query_text], dry_run=False)[0]
                embeddings_cache[cache_key] = query_embedding
            else:
                query_embedding = embeddings_cache[cache_key]

            # Execute search
            search_query = SelectQuery(entity_type=EntityType.SUBSCRIPTION, query_text=query_text, limit=10)

            with db.session as session:
                response = await engine.execute_search(
                    query=search_query, db_session=session, cursor=None, query_embedding=query_embedding
                )

            # Record results
            expected_ranking = [str(r.entity_id) for r in response.results]

            queries.append(
                {
                    "query_text": query_text,
                    "description": query_data["description"],
                    "query_embedding": query_embedding,
                    "expected_ranking": expected_ranking,
                }
            )

    console.print(f"[green]✓[/green] Recorded {len(queries)} ground truth queries with rankings")
    return queries


async def record_ground_truth():
    """Record ground truth embeddings and rankings.

    This function is called by the --record flag in conftest.py.
    It sets up test data, generates embeddings, and records query rankings.
    """
    console.print("\n[bold blue]Recording Ground Truth Data[/bold blue]\n")
    console.print(f"Model: [cyan]{llm_settings.EMBEDDING_MODEL}[/cyan]")
    console.print(f"Dimension: [cyan]{llm_settings.EMBEDDING_DIMENSION}[/cyan]")
    console.print(f"Output: [cyan]{GROUND_TRUTH_FILE}[/cyan]\n")

    # Step 1: Set up test data
    console.print("[bold]Step 1/4:[/bold] Setting up test data...")
    product = ProductTable(**TEST_PRODUCT)
    db.session.add(product)
    db.session.flush()

    subscriptions = []
    for sub_data in TEST_SUBSCRIPTIONS:
        subscription = SubscriptionTable(
            subscription_id=sub_data["subscription_id"],
            description=sub_data["description"],
            product_id=product.product_id,
            customer_id=sub_data["customer_id"],
            insync=sub_data["insync"],
            status=sub_data["status"],
        )
        subscriptions.append(subscription)
        db.session.add(subscription)

    db.session.commit()
    console.print(f"[green]✓[/green] Created {len(subscriptions)} test subscriptions")

    # Step 2: Generate entity embeddings
    console.print("[bold]Step 2/4:[/bold] Generating entity embeddings...")
    entity_embeddings = await generate_entity_embeddings()

    # Step 3: Index subscriptions with embeddings
    console.print("[bold]Step 3/4:[/bold] Indexing subscriptions...")
    for sub in subscriptions:
        embedding = entity_embeddings[sub.description.lower()]
        index_subscription(sub, embedding, db.session)
    db.session.commit()
    console.print(f"[green]✓[/green] Indexed {len(subscriptions)} subscriptions")

    # Prepare entity data
    entities = [
        {
            "subscription_id": str(sub["subscription_id"]),
            "description": sub["description"],
            "customer_id": str(sub["customer_id"]),
            "insync": sub["insync"],
            "status": sub["status"].value if hasattr(sub["status"], "value") else str(sub["status"]),
            "embedding": entity_embeddings[sub["description"].lower()],
        }
        for sub in TEST_SUBSCRIPTIONS
    ]

    # Step 4: Record all ground truth queries with rankings
    console.print("[bold]Step 4/4:[/bold] Recording ground truth queries...")
    queries = await record_ground_truth_queries(entity_embeddings)

    # Save to file
    console.print("[bold]Saving ground truth...[/bold]")
    save_ground_truth(entities, queries)
    console.print(f"[green]✓[/green] Saved ground truth to {GROUND_TRUTH_FILE}")

    console.print("\n[bold green]✓ Recording complete![/bold green]")
    console.print("\nRecorded:")
    console.print(f"  • {len(entities)} entities with embeddings")
    console.print(f"  • {len(queries)} queries with embeddings and rankings")
    console.print(f"\nModel: {llm_settings.EMBEDDING_MODEL}")
    console.print(f"Dimension: {llm_settings.EMBEDDING_DIMENSION}")
