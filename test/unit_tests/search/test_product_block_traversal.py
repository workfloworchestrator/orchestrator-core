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

"""Tests for ProductBlockTraverser: field extraction from ProductBlockTable *definitions*.

Only definition-level metadata (name, description, tag, status, resource types, and
one layer of ``in_use_by`` block relations) is expected — never subscription/instance data.
"""

from datetime import datetime
from uuid import UUID

from orchestrator.core.db import ProductBlockTable, ResourceTypeTable
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.indexing.registry import ENTITY_CONFIG_REGISTRY

_PRODUCT_BLOCK_ID = UUID("770e8400-e29b-41d4-a716-446655440000")
_RESOURCE_TYPE_ID = UUID("880e8400-e29b-41d4-a716-446655440000")
_PARENT_BLOCK_ID = UUID("990e8400-e29b-41d4-a716-446655440000")


def _build_product_block() -> ProductBlockTable:
    resource_type = ResourceTypeTable(
        resource_type_id=_RESOURCE_TYPE_ID,
        resource_type="ipv4_address",
        description="IPv4 address",
    )
    parent_block = ProductBlockTable(
        product_block_id=_PARENT_BLOCK_ID,
        name="parent_block",
        description="Parent block description",
        tag="PARENT",
        status="active",
        created_at=datetime(2024, 1, 15, 10, 30, 0),
    )
    block = ProductBlockTable(
        product_block_id=_PRODUCT_BLOCK_ID,
        name="test_block",
        description="Test block description",
        tag="TEST",
        status="active",
        created_at=datetime(2024, 1, 15, 10, 30, 0),
    )
    block.resource_types = [resource_type]
    block.in_use_by = [parent_block]
    return block


_EXPECTED_FIELDS = {
    "product_block.product_block_id": (str(_PRODUCT_BLOCK_ID), FieldType.UUID),
    "product_block.name": ("test_block", FieldType.STRING),
    "product_block.description": ("Test block description", FieldType.STRING),
    "product_block.tag": ("TEST", FieldType.STRING),
    "product_block.status": ("active", FieldType.STRING),
    "product_block.resource_types.0.resource_type": ("ipv4_address", FieldType.STRING),
    "product_block.in_use_by.0.name": ("parent_block", FieldType.STRING),
}


def test_traverse_product_block_definition():
    block = _build_product_block()

    config = ENTITY_CONFIG_REGISTRY[EntityType.METADATA_PRODUCT_BLOCK]
    extracted_fields = config.traverser.get_fields(entity=block, pk_name=config.pk_name, root_name=config.root_name)
    field_map = {field.path: field for field in extracted_fields}

    for path, (expected_value, expected_type) in _EXPECTED_FIELDS.items():
        assert path in field_map, f"Missing field: {path}"
        assert field_map[path].value_type == expected_type
        assert field_map[path].value == expected_value


def test_traverse_product_block_definition_excludes_nested_in_use_by_relations():
    """`in_use_by` is summarized one layer deep only — no nested relation fields."""
    block = _build_product_block()

    config = ENTITY_CONFIG_REGISTRY[EntityType.METADATA_PRODUCT_BLOCK]
    extracted_fields = config.traverser.get_fields(entity=block, pk_name=config.pk_name, root_name=config.root_name)
    paths = {field.path for field in extracted_fields}

    assert not any(path.startswith("product_block.in_use_by.0.in_use_by") for path in paths)
    assert not any("depends_on" in path for path in paths)
