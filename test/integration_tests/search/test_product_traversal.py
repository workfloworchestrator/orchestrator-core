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

# Asserts on log output via pytest's ``caplog``. Requires
# ``OrchestratorCore.__init__`` to have configured ``structlog`` with
# ``stdlib.LoggerFactory`` so structlog records propagate to stdlib logging
# (and therefore to ``caplog``). The integration conftest boots the app and
# so installs the bridge; the unit conftest does not.

from unittest.mock import MagicMock, patch

from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.core.search.indexing.traverse import ProductTraverser


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
