"""Tests for orchestrator.core.search.filters: StringFilter validation, PathFilter path transformation, FilterTree depth validation, and tree helper methods."""

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

from orchestrator.core.search.core.types import BooleanOperator, FilterOp
from orchestrator.core.search.filters import FilterTree, PathFilter, StringFilter

pytestmark = pytest.mark.search


# ---------------------------------------------------------------------------
# StringFilter LIKE pattern validation
# ---------------------------------------------------------------------------


def test_string_filter_like_without_wildcard_raises_error() -> None:
    with pytest.raises(ValidationError) as exc:
        StringFilter(op=FilterOp.LIKE, value="test")
    assert "wildcard" in str(exc.value).lower()


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("%test%", id="percent-wildcard"),
        pytest.param("test_", id="underscore-wildcard"),
    ],
)
def test_string_filter_like_with_wildcard_succeeds(value: str) -> None:
    f = StringFilter(op=FilterOp.LIKE, value=value)
    assert f.value == value


# ---------------------------------------------------------------------------
# PathFilter path-to-value transformation for path-only operators
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "op, path, expected_path, expected_value",
    [
        pytest.param(
            "has_component",
            "subscription.product",
            "*",
            "subscription.product",
            id="has-component-without-value-transforms",
        ),
        pytest.param(
            "not_has_component",
            "subscription.customer",
            "*",
            "subscription.customer",
            id="not-has-component-without-value-transforms",
        ),
    ],
)
def test_path_filter_path_only_op_without_value_transforms(
    op: str, path: str, expected_path: str, expected_value: str
) -> None:
    data = {
        "path": path,
        "condition": {"op": op},
        "value_kind": "component",
    }
    f = PathFilter.model_validate(data)
    assert f.path == expected_path
    assert f.condition.value == expected_value


def test_path_filter_has_component_with_value_no_transformation() -> None:
    data = {
        "path": "subscription",
        "condition": {"op": "has_component", "value": "product"},
        "value_kind": "component",
    }
    f = PathFilter.model_validate(data)
    assert f.path == "subscription"
    assert f.condition.value == "product"


# ---------------------------------------------------------------------------
# FilterTree depth validation
# ---------------------------------------------------------------------------


def test_filter_tree_depth_exceeds_max_raises_error(path_filter_leaf: PathFilter) -> None:
    with pytest.raises(ValidationError) as exc:
        tree = FilterTree(op=BooleanOperator.AND, children=[path_filter_leaf])
        for _ in range(FilterTree.MAX_DEPTH - 1):
            tree = FilterTree(op=BooleanOperator.AND, children=[tree])
    assert "MAX_DEPTH" in str(exc.value)


def test_filter_tree_depth_at_max_succeeds(path_filter_leaf: PathFilter) -> None:
    tree = FilterTree(op=BooleanOperator.AND, children=[path_filter_leaf])
    for _ in range(FilterTree.MAX_DEPTH - 2):
        tree = FilterTree(op=BooleanOperator.AND, children=[tree])

    validated = FilterTree.model_validate(tree.model_dump())
    assert validated is not None


# ---------------------------------------------------------------------------
# FilterTree helper methods
# ---------------------------------------------------------------------------


def test_get_all_paths_from_nested_tree(nested_filter_tree: FilterTree) -> None:
    paths = nested_filter_tree.get_all_paths()
    assert paths == {"subscription.status", "subscription.product.name", "subscription.customer_id"}


def test_get_all_leaves_from_nested_tree(nested_filter_tree: FilterTree) -> None:
    leaves = nested_filter_tree.get_all_leaves()
    assert len(leaves) == 3
