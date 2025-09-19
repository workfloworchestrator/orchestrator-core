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

from orchestrator.db import ProcessTable, SubscriptionTable
from orchestrator.search.core.exceptions import ModelLoadError, ProductNotInRegistryError
from orchestrator.search.indexing.traverse import ProcessTraverser, ProductTraverser, SubscriptionTraverser


class TestTraverserExceptions:

    def test_subscription_traverser_product_not_in_registry(self):
        """Test SubscriptionTraverser raises ProductNotInRegistryError when product not in registry."""
        mock_subscription = MagicMock(spec=SubscriptionTable)
        mock_product = MagicMock()
        mock_product.name = "NonExistentProduct"
        mock_subscription.product = mock_product

        with pytest.raises(ProductNotInRegistryError, match="Product 'NonExistentProduct' not in registry"):
            SubscriptionTraverser._load_model(mock_subscription)

    def test_subscription_traverser_model_load_error(self):
        """Test SubscriptionTraverser raises ModelLoadError when model creation fails."""
        mock_subscription = MagicMock(spec=SubscriptionTable)
        mock_subscription.subscription_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        mock_product = MagicMock()
        mock_product.name = "ExistingProduct"
        mock_subscription.product = mock_product
        mock_subscription.status = "active"

        mock_model_class = MagicMock()

        with patch("orchestrator.search.indexing.traverse.SUBSCRIPTION_MODEL_REGISTRY") as mock_registry:
            mock_registry.get.return_value = mock_model_class

            with patch("orchestrator.search.indexing.traverse.lookup_specialized_type") as mock_lookup:
                mock_specialized_class = MagicMock()
                mock_lookup.return_value = mock_specialized_class
                mock_specialized_class.from_subscription.side_effect = ValueError("Some error")

                with pytest.raises(ModelLoadError, match="Failed to load model for subscription_id"):
                    SubscriptionTraverser._load_model(mock_subscription)

    def test_process_traverser_model_load_error(self):
        """Test ProcessTraverser raises ModelLoadError when ProcessSchema validation fails."""
        # Create an invalid process that will fail validation
        mock_process = MagicMock(spec=ProcessTable)
        mock_process.process_id = "invalid-uuid"

        with pytest.raises(ModelLoadError, match="Failed to load ProcessSchema for process_id"):
            ProcessTraverser._load_model(mock_process)

    def test_get_fields_handles_product_not_in_registry(self, caplog):
        """get_fields should catch ProductNotInRegistryError and return []."""
        mock_entity = MagicMock()
        mock_entity.subscription_id = UUID("550e8400-e29b-41d4-a716-446655440000")

        with patch.object(SubscriptionTraverser, "_load_model", side_effect=ProductNotInRegistryError("not found")):
            result = SubscriptionTraverser.get_fields(mock_entity, "subscription_id", "root")

        assert result == []
        assert "Failed to extract fields" in caplog.text

    def test_get_fields_handles_load_model_returns_none(self):
        """get_fields should return [] when _load_model returns None."""
        mock_entity = MagicMock()
        mock_entity.subscription_id = UUID("550e8400-e29b-41d4-a716-446655440000")

        with patch.object(SubscriptionTraverser, "_load_model", return_value=None):
            result = SubscriptionTraverser.get_fields(mock_entity, "subscription_id", "root")

        assert result == []

    def test_product_get_fields_handles_load_model_returns_none(self):
        """ProductTraverser.get_fields should return [] when _load_model returns None."""
        mock_product = MagicMock()
        mock_product.product_id = "test-123"

        with patch.object(ProductTraverser, "_load_model", return_value=None):
            result = ProductTraverser.get_fields(mock_product, "product_id", "product")

        assert result == []

    def test_get_fields_handles_product_not_in_registry_error(self, caplog):
        """Test that ProductNotInRegistryError is caught and logged properly."""
        mock_product = MagicMock()
        mock_product.product_id = "test-123"

        with patch.object(ProductTraverser, "_load_model", side_effect=ProductNotInRegistryError("Product not found")):
            result = ProductTraverser.get_fields(mock_product, "product_id", "product")

        assert result == []
        assert "Failed to extract fields from" in caplog.text
        assert "Product not found" in caplog.text

    def test_get_fields_handles_model_load_error(self, caplog):
        """Test that ModelLoadError is caught and logged properly."""
        mock_product = MagicMock()
        mock_product.product_id = "test-456"

        with patch.object(ProductTraverser, "_load_model", side_effect=ModelLoadError("Failed to load model")):
            result = ProductTraverser.get_fields(mock_product, "product_id", "product")

        assert result == []
        assert "Failed to extract fields from" in caplog.text
        assert "Failed to load model" in caplog.text

    def test_get_fields_unexpected_exception_propagates(self):
        """Test that unexpected exceptions are not caught and propagate up."""
        mock_product = MagicMock()
        mock_product.product_id = "test-789"

        with patch.object(ProductTraverser, "_load_model", side_effect=ValueError("Unexpected error")):
            with pytest.raises(ValueError, match="Unexpected error"):
                ProductTraverser.get_fields(mock_product, "product_id", "product")

    def test_traverse_handles_computed_property_exception(self, caplog):
        """Test that traverse() handles computed property exceptions."""
        from pydantic import BaseModel, computed_field

        from orchestrator.search.indexing.traverse import BaseTraverser

        class TestModel(BaseModel):
            normal_field: str = "test_value"

            @computed_field  # type:ignore[misc]
            @property
            def failing_computed_field(self) -> str:
                raise AssertionError("Computed property failed")

        instance = TestModel()

        fields = list(BaseTraverser.traverse(instance, "test"))

        # Should get the normal field but skip the failing computed field
        field_paths = [field.path for field in fields]
        assert "test.normal_field" in field_paths
        assert "test.failing_computed_field" not in field_paths

        # Should log the error
        assert "Failed to access field 'failing_computed_field'" in caplog.text
        assert "Computed property failed" in caplog.text
        assert any(record.levelname == "ERROR" for record in caplog.records)
