"""Tests for ProductTraverser: end-to-end field extraction, ltree sanitization, load_model error handling."""

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

import pytest

from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.core.domain.lifecycle import ProductLifecycle
from orchestrator.core.search.core.exceptions import ProductNotInRegistryError
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.indexing.registry import ENTITY_CONFIG_REGISTRY
from orchestrator.core.search.indexing.traverse import ProductTraverser

from .fixtures.expected_data.products import (
    get_complex_product_expected_fields,
    get_computed_product_expected_fields,
    get_nested_product_expected_fields,
    get_simple_product_expected_fields,
)


def _assert_key_patterns_covered(mock_product_load_model, mock_db_product, product_instance, expected_patterns):
    mock_product_load_model.return_value = product_instance
    config = ENTITY_CONFIG_REGISTRY[EntityType.PRODUCT]

    extracted_fields = config.traverser.get_fields(
        entity=mock_db_product, pk_name=config.pk_name, root_name=config.root_name
    )

    actual_fields_map = {field.path: field for field in extracted_fields}
    expected_paths = {field.path for field in expected_patterns}
    missing_patterns = expected_paths - set(actual_fields_map)
    assert not missing_patterns, f"Missing key patterns: {missing_patterns}"

    for expected_field in expected_patterns:
        actual_field = actual_fields_map[expected_field.path]
        assert actual_field.value == expected_field.value, f"Value mismatch for {expected_field.path}"
        assert actual_field.value_type == expected_field.value_type, f"Type mismatch for {expected_field.path}"


@pytest.mark.parametrize(
    "instance_fixture,expected_fn",
    [
        pytest.param("simple_subscription_instance", get_simple_product_expected_fields, id="simple"),
        pytest.param("nested_subscription_instance", get_nested_product_expected_fields, id="nested"),
        pytest.param("subscription_instance", get_complex_product_expected_fields, id="complex"),
        pytest.param("computed_property_subscription_instance", get_computed_product_expected_fields, id="computed"),
    ],
)
def test_traverse_product(
    request, mock_product_load_model, mock_db_product, product_uuid, instance_fixture, expected_fn
):
    instance = request.getfixturevalue(instance_fixture)
    expected = expected_fn(product_uuid)
    _assert_key_patterns_covered(mock_product_load_model, mock_db_product, instance, expected)


# --- _sanitize_for_ltree ---


@pytest.mark.parametrize(
    "name,expected",
    [
        pytest.param("@#$%^&*()", "unnamed_product", id="all-invalid"),
        pytest.param("My@Product#Name!", "my_product_name", id="mixed-invalid"),
    ],
)
def test_sanitize_for_ltree(name: str, expected: str):
    assert ProductTraverser._sanitize_for_ltree(name) == expected


# --- _load_model ---


def test_product_not_in_registry_raises_error():
    mock_product = MagicMock()
    mock_product.name = "MissingProduct"

    with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {}, clear=True):
        with pytest.raises(ProductNotInRegistryError, match="Product 'MissingProduct' not in registry"):
            ProductTraverser._load_model(mock_product)


def test_successful_load_model(product_uuid):
    mock_product = MagicMock()
    mock_product.name = "MyProduct"
    mock_product.product_id = product_uuid
    mock_product.description = "Test Product"
    mock_product.product_type = "Test"
    mock_product.tag = "TEST"
    mock_product.status = ProductLifecycle.ACTIVE
    mock_product.fixed_inputs = []

    mock_domain_cls = MagicMock()
    mock_specialized_cls = MagicMock()
    mock_specialized_cls._init_instances.return_value = {}

    with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"MyProduct": mock_domain_cls}, clear=True):
        with patch(
            "orchestrator.core.search.indexing.traverse.lookup_specialized_type", return_value=mock_specialized_cls
        ):
            result = ProductTraverser._load_model(mock_product)

    assert result is not None
    mock_specialized_cls._init_instances.assert_called_once()


def test_lookup_specialized_type_fallback(product_uuid):
    mock_product = MagicMock()
    mock_product.name = "MyProduct"
    mock_product.product_id = product_uuid
    mock_product.description = "Test Product"
    mock_product.product_type = "Test"
    mock_product.tag = "TEST"
    mock_product.status = ProductLifecycle.ACTIVE
    mock_product.fixed_inputs = []

    mock_domain_cls = MagicMock()
    mock_domain_cls._init_instances.return_value = {}

    with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"MyProduct": mock_domain_cls}, clear=True):
        with patch("orchestrator.core.search.indexing.traverse.lookup_specialized_type", side_effect=Exception("boom")):
            result = ProductTraverser._load_model(mock_product)

    assert result is not None
    mock_domain_cls._init_instances.assert_called_once()


def test_from_product_id_failure_returns_none(caplog):
    mock_product = MagicMock()
    mock_product.name = "MyProduct"
    mock_product.product_id = "product-123"

    mock_domain_cls = MagicMock()
    mock_domain_cls.from_product_id.side_effect = RuntimeError("db error")

    with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"MyProduct": mock_domain_cls}, clear=True):
        with patch("orchestrator.core.search.indexing.traverse.lookup_specialized_type", return_value=mock_domain_cls):
            result = ProductTraverser._load_model(mock_product)

    assert result is None
    assert "Failed to instantiate template model for product" in caplog.text
