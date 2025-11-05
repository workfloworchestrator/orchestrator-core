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


import pytest
from pydantic import ValidationError

from orchestrator.search.core.types import BooleanOperator, FilterOp, UIType
from orchestrator.search.filters import EqualityFilter, FilterTree, PathFilter, StringFilter

pytestmark = pytest.mark.search


class TestStringFilterValidation:
    """Test StringFilter LIKE pattern validation."""

    def test_like_without_wildcard_raises_error(self):
        """Test that LIKE operation without wildcard raises ValueError."""
        with pytest.raises(ValidationError) as exc:
            StringFilter(op=FilterOp.LIKE, value="test")
        assert "wildcard" in str(exc.value).lower()

    def test_like_with_percent_wildcard(self):
        """Test LIKE operation with % wildcard succeeds."""
        filter = StringFilter(op=FilterOp.LIKE, value="%test%")
        assert filter.value == "%test%"

    def test_like_with_underscore_wildcard(self):
        """Test LIKE operation with _ wildcard succeeds."""
        filter = StringFilter(op=FilterOp.LIKE, value="test_")
        assert filter.value == "test_"


class TestPathFilterTransformation:
    """Test PathFilter path-to-value transformation for path-only operators."""

    def test_has_component_without_value_transforms_path(self):
        """Test has_component without value moves path to value and sets path to '*'."""
        data = {
            "path": "subscription.product",
            "condition": {"op": "has_component"},
            "value_kind": "component",
        }
        filter = PathFilter.model_validate(data)

        assert filter.path == "*"
        assert filter.condition.value == "subscription.product"

    def test_has_component_with_value_no_transformation(self):
        """Test has_component with explicit value doesn't transform."""
        data = {
            "path": "subscription",
            "condition": {"op": "has_component", "value": "product"},
            "value_kind": "component",
        }
        filter = PathFilter.model_validate(data)

        assert filter.path == "subscription"
        assert filter.condition.value == "product"

    def test_not_has_component_without_value_transforms_path(self):
        """Test not_has_component without value transforms path."""
        data = {
            "path": "subscription.customer",
            "condition": {"op": "not_has_component"},
            "value_kind": "component",
        }
        filter = PathFilter.model_validate(data)

        assert filter.path == "*"
        assert filter.condition.value == "subscription.customer"


class TestFilterTreeDepthValidation:
    """Test FilterTree depth validation."""

    def test_depth_exceeds_max_raises_error(self, path_filter_leaf: PathFilter):
        """Test that FilterTree depth > MAX_DEPTH raises ValueError."""
        # Build nested tree: depth = MAX_DEPTH + 1, validation happens during construction
        with pytest.raises(ValidationError) as exc:
            tree = FilterTree(op=BooleanOperator.AND, children=[path_filter_leaf])
            for _ in range(FilterTree.MAX_DEPTH - 1):
                tree = FilterTree(op=BooleanOperator.AND, children=[tree])
        assert "MAX_DEPTH" in str(exc.value)

    def test_depth_at_max_succeeds(self, path_filter_leaf: PathFilter):
        """Test that FilterTree at MAX_DEPTH succeeds."""
        # Build nested tree: depth = MAX_DEPTH
        # Starting depth: tree with leaf = 2
        # Each iteration adds 1 to depth
        tree = FilterTree(op=BooleanOperator.AND, children=[path_filter_leaf])
        for _ in range(FilterTree.MAX_DEPTH - 2):
            tree = FilterTree(op=BooleanOperator.AND, children=[tree])

        # Should not raise
        validated = FilterTree.model_validate(tree.model_dump())
        assert validated is not None


class TestFilterTreeHelpers:
    """Test FilterTree helper methods for traversing the tree."""

    def test_get_all_paths_from_nested_tree(self, nested_filter_tree: FilterTree):
        """Test get_all_paths returns all unique paths from nested tree."""
        paths = nested_filter_tree.get_all_paths()
        assert paths == {"subscription.status", "subscription.product.name", "subscription.customer_id"}

    def test_get_all_leaves_from_nested_tree(self, nested_filter_tree: FilterTree):
        """Test get_all_leaves returns all PathFilter leaves."""
        leaves = nested_filter_tree.get_all_leaves()
        assert len(leaves) == 3
