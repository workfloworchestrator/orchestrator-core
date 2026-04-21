# Copyright 2019-2020 SURF.
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

"""Tests for get_query_loaders_for_model_paths: path resolution, deduplication, subpath filtering, and partial matches."""

from unittest.mock import MagicMock, patch

import pytest

from orchestrator.core.db.loaders import AttrLoader, get_query_loaders_for_model_paths


def _make_attr_loader(name: str = "field") -> AttrLoader:
    loader_fn = MagicMock(name=f"{name}_loader_fn")
    loader_fn.__name__ = "selectinload"
    attr = MagicMock(name=f"{name}_attr")
    next_model = MagicMock(name=f"{name}_next_model")
    return AttrLoader(loader_fn=loader_fn, attr=attr, next_model=next_model)


def _make_joined_loader(result: MagicMock) -> MagicMock:
    """Create a mock Load object that _join_attr_loaders would produce."""
    load = MagicMock()
    load.path = result
    return load


@pytest.fixture()
def _clear_model_loaders():
    """Ensure _MODEL_LOADERS is populated via our mock, not leftover state."""
    with patch("orchestrator.db.loaders._MODEL_LOADERS", {}):
        yield


def test_empty_paths_returns_empty(_clear_model_loaders) -> None:
    root = MagicMock()
    with patch("orchestrator.db.loaders._lookup_attr_loaders", return_value=[]):
        result = get_query_loaders_for_model_paths(root, [])
    assert result == []


def test_single_level_path(_clear_model_loaders) -> None:
    """A single-segment path like 'products' resolves to one loader."""
    root = MagicMock()
    loader = _make_attr_loader("products")

    with patch("orchestrator.db.loaders._lookup_attr_loaders", return_value=[loader]):
        result = get_query_loaders_for_model_paths(root, ["products"])

    assert len(result) == 1


def test_multi_level_path(_clear_model_loaders) -> None:
    """A dotted path like 'products.blocks' resolves through two lookups."""
    root = MagicMock()
    loader_products = _make_attr_loader("products")
    loader_blocks = _make_attr_loader("blocks")

    def lookup(model, field):
        if field == "products":
            return [loader_products]
        if field == "blocks":
            return [loader_blocks]
        return []

    with patch("orchestrator.db.loaders._lookup_attr_loaders", side_effect=lookup):
        result = get_query_loaders_for_model_paths(root, ["products.blocks"])

    assert len(result) == 1


def test_unknown_field_produces_no_loader(_clear_model_loaders) -> None:
    """A path that doesn't match any relationship is silently skipped."""
    root = MagicMock()

    with patch("orchestrator.db.loaders._lookup_attr_loaders", return_value=[]):
        result = get_query_loaders_for_model_paths(root, ["nonexistent"])

    assert result == []


def test_partial_match_stops_at_unknown_segment(_clear_model_loaders) -> None:
    """'products.nonexistent' matches 'products' but stops at the unknown second segment."""
    root = MagicMock()
    loader_products = _make_attr_loader("products")

    def lookup(model, field):
        if field == "products":
            return [loader_products]
        return []

    with patch("orchestrator.db.loaders._lookup_attr_loaders", side_effect=lookup):
        result = get_query_loaders_for_model_paths(root, ["products.nonexistent"])

    # Partial match on 'products' still produces a loader
    assert len(result) == 1


def test_duplicate_paths_deduplicated(_clear_model_loaders) -> None:
    """Identical paths in input only produce one loader."""
    root = MagicMock()
    loader = _make_attr_loader("products")

    with patch("orchestrator.db.loaders._lookup_attr_loaders", return_value=[loader]):
        result = get_query_loaders_for_model_paths(root, ["products", "products"])

    assert len(result) == 1


def test_subpath_filtered_when_longer_path_exists(_clear_model_loaders) -> None:
    """'products' is skipped when 'products.blocks' already matched (longer paths are processed first)."""
    root = MagicMock()
    loader_products = _make_attr_loader("products")
    loader_blocks = _make_attr_loader("blocks")

    def lookup(model, field):
        if field == "products":
            return [loader_products]
        if field == "blocks":
            return [loader_blocks]
        return []

    with patch("orchestrator.db.loaders._lookup_attr_loaders", side_effect=lookup):
        result = get_query_loaders_for_model_paths(root, ["products", "products.blocks"])

    # Only the longer path 'products.blocks' should produce a loader
    assert len(result) == 1


def test_independent_paths_both_included(_clear_model_loaders) -> None:
    """Two unrelated paths like 'products' and 'workflows' each get their own loader."""
    root = MagicMock()
    loader_products = _make_attr_loader("products")
    loader_workflows = _make_attr_loader("workflows")

    def lookup(model, field):
        if field == "products":
            return [loader_products]
        if field == "workflows":
            return [loader_workflows]
        return []

    with patch("orchestrator.db.loaders._lookup_attr_loaders", side_effect=lookup):
        result = get_query_loaders_for_model_paths(root, ["products", "workflows"])

    assert len(result) == 2
