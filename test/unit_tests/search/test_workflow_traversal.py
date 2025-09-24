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


class TestWorkflowTraverser:
    """Simple test for WorkflowTraverser focusing on basic field extraction."""

    def test_traverse_simple_workflow(self):
        """Test basic workflow field extraction."""
        # Create real WorkflowTable entity
        workflow_id = UUID("660e8400-e29b-41d4-a716-446655440000")

        workflow = WorkflowTable(
            workflow_id=workflow_id,
            name="test_workflow",
            target=Target.CREATE,
            description="Test workflow description",
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            is_task=False,
        )

        config = ENTITY_CONFIG_REGISTRY[EntityType.WORKFLOW]
        extracted_fields = config.traverser.get_fields(
            entity=workflow, pk_name=config.pk_name, root_name=config.root_name
        )

        field_map = {field.path: field for field in extracted_fields}

        assert "workflow.workflow_id" in field_map
        assert field_map["workflow.workflow_id"].value == "660e8400-e29b-41d4-a716-446655440000"
        assert field_map["workflow.workflow_id"].value_type == FieldType.UUID

        assert "workflow.name" in field_map
        assert field_map["workflow.name"].value == "test_workflow"
        assert field_map["workflow.name"].value_type == FieldType.STRING

        assert "workflow.target" in field_map
        assert field_map["workflow.target"].value == "CREATE"
        assert field_map["workflow.target"].value_type == FieldType.STRING

        assert "workflow.description" in field_map
        assert field_map["workflow.description"].value == "Test workflow description"
        assert field_map["workflow.description"].value_type == FieldType.STRING

        assert "workflow.created_at" in field_map
        assert field_map["workflow.created_at"].value_type == FieldType.DATETIME

        assert "workflow.is_task" in field_map
        assert field_map["workflow.is_task"].value == "False"
        assert field_map["workflow.is_task"].value_type == FieldType.BOOLEAN
