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
import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.db import ProductTable, SubscriptionTable, db
from orchestrator.db.models import AiSearchIndex
from orchestrator.llm_settings import llm_settings
from orchestrator.search.core.types import EntityType

from .fixtures import TEST_PRODUCT, TEST_SUBSCRIPTIONS
from .helpers import index_subscription, load_ground_truth


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--record",
        action="store_true",
        default=False,
        help="Record ground truth embeddings and rankings (regenerates ground_truth.json)",
    )
    parser.addoption(
        "--benchmark",
        action="store_true",
        default=False,
        help="Run benchmark comparing embedding models",
    )


@pytest.fixture(scope="session", autouse=True)
def maybe_record_ground_truth(request, worker_id, database):
    """Record ground truth if --record flag is passed, then exit.

    This runs before any tests and generates the ground truth dataset if requested.
    After recording, pytest exits to prevent running regular tests with the recording setup.

    """
    if not request.config.getoption("--record"):
        return

    if worker_id != "master":
        pytest.exit("Ground truth recording only runs on main worker")

    # Suspend output capturing for benchmark
    capman = request.config.pluginmanager.get_plugin("capturemanager")
    if capman:
        capman.suspend_global_capture(in_=True)

    from test.integration_tests.search.scripts.record_ground_truth import record_ground_truth

    # Run the recording
    try:
        asyncio.run(record_ground_truth())
    except Exception:
        import traceback

        traceback.print_exc()
        os._exit(1)

    os._exit(0)


@pytest.fixture(scope="session", autouse=True)
def maybe_run_benchmark(request, worker_id, database):
    """Run benchmark if --benchmark flag is passed, then exit.

    This runs before any tests and compares embedding models.
    After benchmarking, pytest exits to prevent running regular tests.

    """
    if not request.config.getoption("--benchmark"):
        return

    if worker_id != "master":
        pytest.exit("Benchmark only runs on main worker")

    # Suspend output capturing for benchmark
    capman = request.config.pluginmanager.get_plugin("capturemanager")
    if capman:
        capman.suspend_global_capture(in_=True)

    # Setup test data
    from orchestrator.db import ProductTable, SubscriptionTable

    with db.session as session:
        product = ProductTable(**TEST_PRODUCT)
        session.add(product)
        session.flush()

        for sub_data in TEST_SUBSCRIPTIONS:
            subscription = SubscriptionTable(
                subscription_id=sub_data["subscription_id"],
                description=sub_data["description"],
                product_id=product.product_id,
                customer_id=sub_data["customer_id"],
                insync=sub_data["insync"],
                status=sub_data["status"],
            )
            session.add(subscription)

        session.commit()

    from test.integration_tests.search.scripts.benchmark.benchmark import run_benchmark

    # Run the benchmark
    try:
        asyncio.run(run_benchmark())
    except Exception:
        import traceback

        traceback.print_exc()
        os._exit(1)

    os._exit(0)


@pytest.fixture(scope="session", autouse=True)
def check_search_enabled():
    """Skip all tests in this directory if search is not enabled."""
    if not llm_settings.SEARCH_ENABLED:
        pytest.skip("Search is not enabled, skipping search integration tests")


@pytest.fixture(scope="session")
def embedding_fixtures() -> dict[str, list[float]]:
    """Load recorded embeddings from ground truth file.

    Returns:
        Dictionary mapping text to embedding vectors.
        Includes both entity embeddings and query embeddings.
    """
    ground_truth = load_ground_truth()

    embeddings = {}

    # Add entity embeddings
    for entity in ground_truth.get("entities", []):
        embeddings[entity["description"].lower()] = entity["embedding"]

    # Add query embeddings
    for query in ground_truth.get("queries", []):
        embeddings[query["query_text"].lower()] = query["query_embedding"]

    return embeddings


@pytest.fixture
def mock_embeddings(embedding_fixtures: dict[str, list[float]]):
    """Mock embedding API calls to return recorded embeddings.

    This ensures consistent test results without calling the actual API.
    Only mocks async (llm_aembedding) as it's used during query execution.
    """

    async def mock_embedding_async(model: str, input: list[str], **kwargs) -> MagicMock:
        """Mock async embedding call for query execution."""
        mock_response = MagicMock()
        mock_response.data = []

        for idx, text in enumerate(input):
            embedding = embedding_fixtures.get(text.lower())
            if embedding is None:
                raise ValueError(f"No embedding found for '{text}' in ground_truth.json. ")
            mock_response.data.append({"index": idx, "embedding": embedding})

        return mock_response

    with patch("orchestrator.search.core.embedding.llm_aembedding", side_effect=mock_embedding_async):
        yield


@pytest.fixture
def test_subscriptions(db_session) -> list[SubscriptionTable]:
    """Create test subscriptions with semantic content for search testing.

    These subscriptions contain meaningful descriptions for semantic search testing.
    """
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
    return subscriptions


@pytest.fixture
def indexed_subscriptions(db_session, test_subscriptions, mock_embeddings, embedding_fixtures):
    """Index test subscriptions into AiSearchIndex table.

    This manually indexes subscriptions to test retrieval behavior without needing
    the full product registry setup. The focus is on testing search ranking with
    semantically meaningful descriptions.
    """
    for idx, sub in enumerate(test_subscriptions, start=1):
        embedding = embedding_fixtures.get(sub.description.lower())
        if embedding is None:
            raise ValueError(f"No embedding found for subscription '{sub.description}' in ground_truth.json. ")

        index_subscription(sub, embedding, db.session, subscription_index=idx)

    db.session.commit()

    indexed_count = (
        db.session.query(AiSearchIndex).filter(AiSearchIndex.entity_type == EntityType.SUBSCRIPTION.value).count()
    )

    assert indexed_count > 0, f"Subscriptions should be indexed, found {indexed_count} records"

    return test_subscriptions
