"""Tests for WorkflowTraverser: basic field extraction from WorkflowTable entities."""

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

from datetime import datetime
from uuid import UUID

from orchestrator.db import WorkflowTable
from orchestrator.search.core.types import EntityType, FieldType
from orchestrator.search.indexing.registry import ENTITY_CONFIG_REGISTRY
from orchestrator.targets import Target

_EXPECTED_FIELDS = {
    "workflow.workflow_id": ("660e8400-e29b-41d4-a716-446655440000", FieldType.UUID),
    "workflow.name": ("test_workflow", FieldType.STRING),
    "workflow.target": ("CREATE", FieldType.STRING),
    "workflow.description": ("Test workflow description", FieldType.STRING),
    "workflow.created_at": (None, FieldType.DATETIME),
    "workflow.is_task": ("False", FieldType.BOOLEAN),
}


def test_traverse_simple_workflow():
    workflow = WorkflowTable(
        workflow_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
        name="test_workflow",
        target=Target.CREATE,
        description="Test workflow description",
        created_at=datetime(2024, 1, 15, 10, 30, 0),
        is_task=False,
    )

    config = ENTITY_CONFIG_REGISTRY[EntityType.WORKFLOW]
    extracted_fields = config.traverser.get_fields(entity=workflow, pk_name=config.pk_name, root_name=config.root_name)
    field_map = {field.path: field for field in extracted_fields}

    for path, (expected_value, expected_type) in _EXPECTED_FIELDS.items():
        assert path in field_map, f"Missing field: {path}"
        assert field_map[path].value_type == expected_type
        if expected_value is not None:
            assert field_map[path].value == expected_value
