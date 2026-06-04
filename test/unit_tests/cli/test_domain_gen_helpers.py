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

import pytest

from orchestrator.core.cli.domain_gen_helpers.helpers import (
    _block_type_matches,
    format_block_relation_to_dict,
    map_create_product_block_relations,
)
from orchestrator.core.domain.base import ProductBlockModel


class LeafA(ProductBlockModel, product_block_name="LeafA"):
    a: int | None = None


class LeafB(ProductBlockModel, product_block_name="LeafB"):
    b: int | None = None


class LeafC(ProductBlockModel, product_block_name="LeafC"):
    c: int | None = None


class ContainerBlockInactive(ProductBlockModel, product_block_name="ContainerBlock"):
    # Non-Optional union: `_get_depends_on_product_block_types` yields a tuple of types.
    union_block: LeafA | LeafB | None = None
    single_block: LeafC | None = None


class ContainerBlock(ContainerBlockInactive):
    union_block: LeafA | LeafB
    single_block: LeafC


MODELS = {"ContainerBlock": ContainerBlock}

@pytest.mark.parametrize(
    "block_type, block_to_find, expected",
    [
        pytest.param(LeafA, "LeafA", True, id="single-match"),
        pytest.param(LeafA, "LeafB", False, id="single-no-match"),
        pytest.param((LeafA, LeafB), "LeafA", True, id="union-match-first"),
        pytest.param((LeafA, LeafB), "LeafB", True, id="union-match-second"),
        pytest.param((LeafA, LeafB), "LeafC", False, id="union-no-match"),
        pytest.param((), "LeafA", False, id="empty-tuple"),
    ],
)
def test_block_type_matches(block_type, block_to_find, expected):
    assert _block_type_matches(block_type, block_to_find) is expected


@pytest.mark.parametrize(
    "block_to_find, expected_attribute",
    [
        pytest.param("LeafC", "single_block", id="single-block-relation"),
        # Regression: a union member must resolve to the union attribute instead of crashing.
        pytest.param("LeafA", "union_block", id="union-block-relation-first-member"),
        pytest.param("LeafB", "union_block", id="union-block-relation-second-member"),
    ],
)
def test_format_block_relation_to_dict_resolves_attribute(block_to_find, expected_attribute):
    result = format_block_relation_to_dict("ContainerBlock", block_to_find, MODELS, confirm_warnings=False)

    assert result == {"name": "ContainerBlock", "attribute_name": expected_attribute}


def test_map_create_product_block_relations_handles_union_member():
    """End-to-end mapper call that previously raised AttributeError on the tuple value."""
    model_diffs = {"ContainerBlock": {"missing_product_blocks_in_db": {"LeafB"}}}

    relations = map_create_product_block_relations(model_diffs, MODELS, confirm_warnings=False)

    assert relations == {"LeafB": [{"name": "ContainerBlock", "attribute_name": "union_block"}]}
