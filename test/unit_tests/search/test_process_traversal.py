"""Tests for ProcessTraverser: basic field extraction from ProcessTable entities."""

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
from unittest.mock import MagicMock
from uuid import UUID

from orchestrator.core.db import ProcessTable
from orchestrator.core.search.core.types import EntityType, FieldType
from orchestrator.core.search.indexing.registry import ENTITY_CONFIG_REGISTRY

_EXPECTED_FIELDS = {
    "process.process_id": ("550e8400-e29b-41d4-a716-446655440000", FieldType.UUID),
    "process.assignee": ("SYSTEM", FieldType.STRING),
    "process.last_status": ("completed", FieldType.STRING),
    "process.started_at": (None, FieldType.DATETIME),
    "process.last_modified_at": (None, FieldType.DATETIME),
    "process.created_by": ("admin", FieldType.STRING),
    "process.is_task": ("True", FieldType.BOOLEAN),
    "process.workflow_name": ("test_workflow", FieldType.STRING),
}


def test_traverse_simple_process():
    process = ProcessTable(
        process_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        workflow_id=UUID("880e8400-e29b-41d4-a716-446655440000"),
        assignee="SYSTEM",
        last_status="completed",
        started_at=datetime(2024, 1, 15, 10, 30, 0),
        last_modified_at=datetime(2024, 1, 15, 11, 0, 0),
        failed_reason=None,
        created_by="admin",
        is_task=True,
    )

    mock_workflow = MagicMock()
    mock_workflow.name = "test_workflow"
    process.workflow = mock_workflow
    process.subscriptions = []

    config = ENTITY_CONFIG_REGISTRY[EntityType.PROCESS]
    extracted_fields = config.traverser.get_fields(entity=process, pk_name=config.pk_name, root_name=config.root_name)
    field_map = {field.path: field for field in extracted_fields}

    for path, (expected_value, expected_type) in _EXPECTED_FIELDS.items():
        assert path in field_map, f"Missing field: {path}"
        assert field_map[path].value_type == expected_type
        if expected_value is not None:
            assert field_map[path].value == expected_value
