from uuid import UUID
from datetime import datetime
from unittest.mock import MagicMock

from orchestrator.db import ProcessTable
from orchestrator.search.core.types import EntityType, FieldType
from orchestrator.search.indexing.registry import ENTITY_CONFIG_REGISTRY


class TestProcessTraverser:
    """Simple test for ProcessTraverser focusing on basic field extraction."""

    def test_traverse_simple_process(self):
        """Test basic process field extraction excluding relational fields."""

        process_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        workflow_id = UUID("880e8400-e29b-41d4-a716-446655440000")

        process = ProcessTable(
            process_id=process_id,
            workflow_id=workflow_id,
            assignee="SYSTEM",
            last_status="completed",
            started_at=datetime(2024, 1, 15, 10, 30, 0),
            last_modified_at=datetime(2024, 1, 15, 11, 0, 0),
            failed_reason=None,
            created_by="admin",
            is_task=True,
        )

        # Mock workflow relationship
        mock_workflow = MagicMock()
        mock_workflow.name = "test_workflow"
        process.workflow = mock_workflow
        process.subscriptions = []

        config = ENTITY_CONFIG_REGISTRY[EntityType.PROCESS]
        extracted_fields = config.traverser.get_fields(
            entity=process, pk_name=config.pk_name, root_name=config.root_name
        )

        field_map = {field.path: field for field in extracted_fields}

        assert "process.process_id" in field_map
        assert field_map["process.process_id"].value == "550e8400-e29b-41d4-a716-446655440000"

        assert field_map["process.process_id"].value_type == FieldType.UUID

        assert "process.assignee" in field_map
        assert field_map["process.assignee"].value == "SYSTEM"
        assert field_map["process.assignee"].value_type == FieldType.STRING

        assert "process.last_status" in field_map
        assert field_map["process.last_status"].value == "completed"
        assert field_map["process.last_status"].value_type == FieldType.STRING

        assert "process.started_at" in field_map
        assert field_map["process.started_at"].value_type == FieldType.DATETIME

        assert "process.last_modified_at" in field_map
        assert field_map["process.last_modified_at"].value_type == FieldType.DATETIME

        assert "process.created_by" in field_map
        assert field_map["process.created_by"].value == "admin"
        assert field_map["process.created_by"].value_type == FieldType.STRING

        assert "process.is_task" in field_map
        assert field_map["process.is_task"].value == "True"
        assert field_map["process.is_task"].value_type == FieldType.BOOLEAN

        assert "process.workflow_name" in field_map
        assert field_map["process.workflow_name"].value == "test_workflow"
        assert field_map["process.workflow_name"].value_type == FieldType.STRING
