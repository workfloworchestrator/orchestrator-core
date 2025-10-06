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

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from orchestrator.domain.base import ProductModel
from orchestrator.search.core.types import ExtractedField

from .fixtures.expected_data.subscriptions import (
    get_complex_expected_fields,
    get_computed_property_expected_fields,
    get_nested_expected_fields,
    get_simple_expected_fields,
)
from .fixtures.factories import (
    create_complex_product_instance,
    create_complex_subscription_instance,
    create_computed_product_instance,
    create_computed_property_subscription_instance,
    create_nested_product_instance,
    create_nested_subscription_instance,
    create_simple_product_instance,
    create_simple_subscription_instance,
)
from .fixtures.subscriptions import (
    ComplexSubscription,
    ComputedPropertySubscription,
    NestedSubscription,
    SimpleSubscription,
)

# Mark all tests in this directory with the search marker
pytestmark = pytest.mark.search


def pytest_ignore_collect(collection_path, config):
    """Ignore collecting tests from this directory when search is disabled."""
    from orchestrator.llm_settings import llm_settings

    # Skip this entire directory if search is disabled
    if not llm_settings.SEARCH_ENABLED:
        return True
    return False


def pytest_addoption(parser):
    parser.addoption(
        "--record",
        action="store_true",
        default=False,
        help="Record SQL snapshots for retriever tests.",
    )


@pytest.fixture
def subscription_uuid() -> UUID:
    return UUID("00000003-0000-0000-0000-000000000003")


@pytest.fixture
def product_uuid() -> UUID:
    return UUID("11110003-0000-0000-0000-000000000003")


@pytest.fixture
def simple_subscription_instance(subscription_uuid: UUID, product_uuid: UUID) -> SimpleSubscription:
    return create_simple_subscription_instance(subscription_uuid, product_uuid)


@pytest.fixture
def nested_subscription_instance(subscription_uuid: UUID, product_uuid: UUID) -> NestedSubscription:
    return create_nested_subscription_instance(subscription_uuid, product_uuid)


@pytest.fixture
def subscription_instance(subscription_uuid: UUID, product_uuid: UUID) -> ComplexSubscription:
    return create_complex_subscription_instance(subscription_uuid, product_uuid)


@pytest.fixture
def mock_db_subscription() -> MagicMock:
    """Provides a mock SQLAlchemy SubscriptionTable object that mimics a real database entity."""

    def create_mock_db_subscription(subscription_id: str = "test-sub-123", product_name: str = "TestProduct"):
        mock_product = MagicMock()
        mock_product.name = product_name
        mock_product.product_type = "Test"
        mock_product.tag = "TEST"
        mock_product.status = "active"

        mock_sub = MagicMock()
        mock_sub.subscription_id = subscription_id
        mock_sub.product = mock_product
        mock_sub.status = "active"
        mock_sub.insync = True
        mock_sub.description = "Test subscription"

        return mock_sub

    return create_mock_db_subscription()


@pytest.fixture
def mock_load_model():
    with patch("orchestrator.search.indexing.traverse.SubscriptionTraverser._load_model") as mock:
        yield mock


@pytest.fixture
def mock_db_product(product_uuid: UUID) -> MagicMock:
    """Provides a mock SQLAlchemy ProductTable object that mimics a real database entity."""
    from orchestrator.domain.lifecycle import ProductLifecycle

    def create_mock_db_product(product_id: UUID | None = None, product_name: str = "TestProduct"):
        mock_product = MagicMock()
        mock_product.product_id = product_id or product_uuid
        mock_product.name = product_name
        mock_product.description = "Test Product Description"
        mock_product.product_type = "Test"
        mock_product.tag = "TEST"
        mock_product.status = ProductLifecycle.ACTIVE
        mock_product.fixed_inputs = []

        return mock_product

    return create_mock_db_product()


@pytest.fixture
def mock_product_load_model():
    with patch("orchestrator.search.indexing.traverse.ProductTraverser._load_model") as mock:
        yield mock


@pytest.fixture
def simple_expected_fields(subscription_uuid: UUID, product_uuid: UUID) -> list[ExtractedField]:
    return get_simple_expected_fields(subscription_uuid, product_uuid)


@pytest.fixture
def nested_expected_fields(subscription_uuid: UUID, product_uuid: UUID) -> list[ExtractedField]:
    return get_nested_expected_fields(subscription_uuid, product_uuid)


@pytest.fixture
def computed_property_subscription_instance(
    subscription_uuid: UUID, product_uuid: UUID
) -> ComputedPropertySubscription:
    return create_computed_property_subscription_instance(subscription_uuid, product_uuid)


@pytest.fixture
def computed_property_expected_fields(subscription_uuid: UUID, product_uuid: UUID) -> list[ExtractedField]:
    return get_computed_property_expected_fields(subscription_uuid, product_uuid)


@pytest.fixture
def expected_traverse_fields(subscription_uuid: UUID, product_uuid: UUID) -> list[ExtractedField]:

    return get_complex_expected_fields(subscription_uuid, product_uuid)


@pytest.fixture
def simple_product_instance(product_uuid: UUID) -> ProductModel:
    return create_simple_product_instance(product_uuid)


@pytest.fixture
def nested_product_instance(product_uuid: UUID) -> ProductModel:
    return create_nested_product_instance(product_uuid)


@pytest.fixture
def complex_product_instance(product_uuid: UUID) -> ProductModel:
    return create_complex_product_instance(product_uuid)


@pytest.fixture
def computed_product_instance(product_uuid: UUID) -> ProductModel:
    return create_computed_product_instance(product_uuid)
