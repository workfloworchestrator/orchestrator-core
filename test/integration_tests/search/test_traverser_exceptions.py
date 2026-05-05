# Copyright 2019-2026 SURF, GÉANT.
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

# These tests assert on log output via pytest's ``caplog``. They require
# OrchestratorCore.__init__ to have configured ``structlog`` with
# ``stdlib.LoggerFactory`` so that structlog log records propagate to stdlib
# logging (and therefore to ``caplog``). Without that bridge, ``caplog.text``
# is empty and the assertions trivially fail. The integration conftest boots
# the app and so installs the bridge; the unit conftest does not.

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from orchestrator.core.search.core.exceptions import ModelLoadError, ProductNotInRegistryError
from orchestrator.core.search.indexing.traverse import ProductTraverser, SubscriptionTraverser


@pytest.mark.parametrize(
    "traverser_cls,entity_attr,entity_id,error_cls",
    [
        pytest.param(
            SubscriptionTraverser,
            "subscription_id",
            UUID("550e8400-e29b-41d4-a716-446655440000"),
            ProductNotInRegistryError("not found"),
            id="subscription-product-not-in-registry",
        ),
        pytest.param(
            ProductTraverser,
            "product_id",
            "test-123",
            ProductNotInRegistryError("Product not found"),
            id="product-not-in-registry",
        ),
        pytest.param(
            ProductTraverser,
            "product_id",
            "test-456",
            ModelLoadError("Failed to load model"),
            id="product-model-load-error",
        ),
    ],
)
def test_get_fields_handles_expected_errors(caplog, traverser_cls, entity_attr, entity_id, error_cls):
    mock_entity = MagicMock()
    setattr(mock_entity, entity_attr, entity_id)

    with patch.object(traverser_cls, "_load_model", side_effect=error_cls):
        result = traverser_cls.get_fields(
            mock_entity, entity_attr, traverser_cls.__name__.replace("Traverser", "").lower()
        )

    assert result == []
    assert "Failed to extract fields" in caplog.text


def test_traverse_handles_computed_property_exception(caplog):
    from pydantic import BaseModel, computed_field

    from orchestrator.core.search.indexing.traverse import BaseTraverser

    class TestModel(BaseModel):
        normal_field: str = "test_value"

        @computed_field  # type: ignore[untyped-decorator]
        @property
        def failing_computed_field(self) -> str:
            raise AssertionError("Computed property failed")

    instance = TestModel()
    fields = list(BaseTraverser.traverse(instance, "test"))

    field_paths = [field.path for field in fields]
    assert "test.normal_field" in field_paths
    assert "test.failing_computed_field" not in field_paths
    assert "Failed to access field 'failing_computed_field'" in caplog.text
    assert "Computed property failed" in caplog.text
    assert any(record.levelname == "ERROR" for record in caplog.records)
