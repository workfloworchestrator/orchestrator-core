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

"""Tests for ResourceTypeTraverser: basic field extraction from ResourceTypeTable entities."""

from uuid import UUID

from orchestrator.core.db import ResourceTypeTable
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.indexing.registry import ENTITY_CONFIG_REGISTRY

_RESOURCE_TYPE_ID = UUID("880e8400-e29b-41d4-a716-446655440000")

_EXPECTED_FIELDS = {
    "resource_type.resource_type_id": (str(_RESOURCE_TYPE_ID), FieldType.UUID),
    "resource_type.resource_type": ("ipv4_address", FieldType.STRING),
    "resource_type.description": ("IPv4 address", FieldType.STRING),
}


def test_traverse_resource_type_definition():
    resource_type = ResourceTypeTable(
        resource_type_id=_RESOURCE_TYPE_ID,
        resource_type="ipv4_address",
        description="IPv4 address",
    )

    config = ENTITY_CONFIG_REGISTRY[EntityType.METADATA_RESOURCE_TYPE]
    extracted_fields = config.traverser.get_fields(
        entity=resource_type, pk_name=config.pk_name, root_name=config.root_name
    )
    field_map = {field.path: field for field in extracted_fields}

    for path, (expected_value, expected_type) in _EXPECTED_FIELDS.items():
        assert path in field_map, f"Missing field: {path}"
        assert field_map[path].value_type == expected_type
        assert field_map[path].value == expected_value
