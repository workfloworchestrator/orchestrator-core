from unittest.mock import MagicMock, patch

import pytest

from orchestrator.search.core.exceptions import ProductNotInRegistryError
from orchestrator.search.core.types import EntityType
from orchestrator.search.indexing.registry import ENTITY_CONFIG_REGISTRY
from orchestrator.search.indexing.traverse import SUBSCRIPTION_MODEL_REGISTRY, ProductTraverser

from .fixtures.expected_data.products import (
    get_complex_product_expected_fields,
    get_computed_product_expected_fields,
    get_nested_product_expected_fields,
    get_simple_product_expected_fields,
)


class TestProductTraverser:
    """Integration tests that product traversal works end-to-end extracting schema information."""

    def _assert_key_patterns_covered(
        self, mock_product_load_model, mock_db_product, product_instance, expected_patterns
    ):
        """Helper to verify that key patterns are covered in traversal results."""
        mock_product_load_model.return_value = product_instance
        config = ENTITY_CONFIG_REGISTRY[EntityType.PRODUCT]

        extracted_fields = config.traverser.get_fields(
            entity=mock_db_product, pk_name=config.pk_name, root_name=config.root_name
        )

        actual_paths = {field.path for field in extracted_fields}
        expected_paths = {field.path for field in expected_patterns}

        missing_patterns = expected_paths - actual_paths
        assert not missing_patterns, f"Missing key patterns: {missing_patterns}"

        actual_fields_map = {field.path: field for field in extracted_fields}
        for expected_field in expected_patterns:
            actual_field = actual_fields_map[expected_field.path]
            assert actual_field.value == expected_field.value, f"Value mismatch for {expected_field.path}"
            assert actual_field.value_type == expected_field.value_type, f"Type mismatch for {expected_field.path}"

    def test_traverse_simple_product(
        self, mock_product_load_model, mock_db_product, simple_subscription_instance, product_uuid
    ) -> None:
        """Verify simple product covers key patterns: metadata + basic block schema."""
        expected_patterns = get_simple_product_expected_fields(product_uuid)
        self._assert_key_patterns_covered(
            mock_product_load_model, mock_db_product, simple_subscription_instance, expected_patterns
        )

    def test_traverse_nested_product(
        self, mock_product_load_model, mock_db_product, nested_subscription_instance, product_uuid
    ) -> None:
        """Verify nested product covers nesting patterns correctly."""
        expected_patterns = get_nested_product_expected_fields(product_uuid)
        self._assert_key_patterns_covered(
            mock_product_load_model, mock_db_product, nested_subscription_instance, expected_patterns
        )

    def test_traverse_complex_product(
        self, mock_product_load_model, mock_db_product, subscription_instance, product_uuid
    ) -> None:
        """Verify complex product covers list and container patterns."""
        expected_patterns = get_complex_product_expected_fields(product_uuid)
        self._assert_key_patterns_covered(
            mock_product_load_model, mock_db_product, subscription_instance, expected_patterns
        )

    def test_traverse_computed_product(
        self, mock_product_load_model, mock_db_product, computed_property_subscription_instance, product_uuid
    ) -> None:
        """Verify computed product covers computed property patterns."""
        expected_patterns = get_computed_product_expected_fields(product_uuid)
        self._assert_key_patterns_covered(
            mock_product_load_model, mock_db_product, computed_property_subscription_instance, expected_patterns
        )


class TestLoadModel:
    def test_product_not_in_registry_raises_error(self):
        mock_product = MagicMock()
        mock_product.name = "MissingProduct"

        with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {}, clear=True):
            with pytest.raises(ProductNotInRegistryError, match="Product 'MissingProduct' not in registry"):
                ProductTraverser._load_model(mock_product)

    def test_successful_load_model(self):
        mock_product = MagicMock()
        mock_product.name = "MyProduct"
        mock_product.product_id = "product-123"

        mock_domain_cls = MagicMock()
        mock_specialized_cls = MagicMock()
        mock_instance = MagicMock()
        mock_specialized_cls.from_product_id.return_value = mock_instance

        with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"MyProduct": mock_domain_cls}, clear=True):
            with patch(
                "orchestrator.search.indexing.traverse.lookup_specialized_type", return_value=mock_specialized_cls
            ):
                result = ProductTraverser._load_model(mock_product)

        assert result == mock_instance
        mock_specialized_cls.from_product_id.assert_called_once_with(
            product_id="product-123", customer_id="traverser_template"
        )

    def test_lookup_specialized_type_fallback(self):
        mock_product = MagicMock()
        mock_product.name = "MyProduct"
        mock_product.product_id = "product-123"

        mock_domain_cls = MagicMock()
        mock_instance = MagicMock()
        mock_domain_cls.from_product_id.return_value = mock_instance

        with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"MyProduct": mock_domain_cls}, clear=True):
            with patch("orchestrator.search.indexing.traverse.lookup_specialized_type", side_effect=Exception("boom")):
                result = ProductTraverser._load_model(mock_product)

        assert result == mock_instance

    def test_from_product_id_failure_returns_none(self, caplog):
        mock_product = MagicMock()
        mock_product.name = "MyProduct"
        mock_product.product_id = "product-123"

        mock_domain_cls = MagicMock()
        mock_domain_cls.from_product_id.side_effect = RuntimeError("db error")

        with patch.dict(SUBSCRIPTION_MODEL_REGISTRY, {"MyProduct": mock_domain_cls}, clear=True):
            with patch("orchestrator.search.indexing.traverse.lookup_specialized_type", return_value=mock_domain_cls):
                result = ProductTraverser._load_model(mock_product)

        assert result is None
        assert "Failed to instantiate template model for product" in caplog.text
