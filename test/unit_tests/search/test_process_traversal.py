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

"""Tests for ProcessTraverser: basic field extraction from ProcessTable entities."""

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
    "process.workflow_target": ("CREATE", FieldType.STRING),
    "process.note": ("Some note", FieldType.STRING),
}


def _build_process() -> ProcessTable:
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
        note="Some note",
    )

    mock_workflow = MagicMock()
    mock_workflow.name = "test_workflow"
    mock_workflow.target = "CREATE"
    process.workflow = mock_workflow
    process.subscriptions = []
    return process


def test_traverse_simple_process():
    process = _build_process()

    config = ENTITY_CONFIG_REGISTRY[EntityType.PROCESS]
    extracted_fields = config.traverser.get_fields(entity=process, pk_name=config.pk_name, root_name=config.root_name)
    field_map = {field.path: field for field in extracted_fields}

    for path, (expected_value, expected_type) in _EXPECTED_FIELDS.items():
        assert path in field_map, f"Missing field: {path}"
        assert field_map[path].value_type == expected_type
        if expected_value is not None:
            assert field_map[path].value == expected_value


def test_traverse_process_with_subscription():
    process = _build_process()

    mock_product = MagicMock()
    mock_product.name = "Test Product"
    mock_product.tag = "TP"

    mock_subscription = MagicMock()
    mock_subscription.subscription_id = UUID("660e8400-e29b-41d4-a716-446655440000")
    mock_subscription.description = "Test subscription"
    mock_subscription.customer_id = "cust-1"
    mock_subscription.product = mock_product
    mock_subscription.customer_name = "Test Customer"
    mock_subscription.customer_abbreviation = "TC"

    mock_process_subscription = MagicMock()
    mock_process_subscription.subscription = mock_subscription
    process.process_subscriptions = [mock_process_subscription]

    config = ENTITY_CONFIG_REGISTRY[EntityType.PROCESS]
    extracted_fields = config.traverser.get_fields(entity=process, pk_name=config.pk_name, root_name=config.root_name)
    field_map = {field.path: field for field in extracted_fields}

    expected = {
        "process.subscriptions.0.subscription_id": "660e8400-e29b-41d4-a716-446655440000",
        "process.subscriptions.0.description": "Test subscription",
        "process.subscriptions.0.customer_id": "cust-1",
        "process.subscriptions.0.product_name": "Test Product",
        "process.subscriptions.0.product_tag": "TP",
        "process.subscriptions.0.customer_name": "Test Customer",
        "process.subscriptions.0.customer_abbreviation": "TC",
    }
    for path, expected_value in expected.items():
        assert path in field_map, f"Missing field: {path}"
        assert field_map[path].value == expected_value


def test_traverse_process_with_subscription_missing_customer_fields():
    """Subscription objects from a generic SubscriptionTable have no customer_name/abbreviation."""
    process = _build_process()

    mock_product = MagicMock()
    mock_product.name = "Test Product"
    mock_product.tag = "TP"

    class GenericSubscription:
        subscription_id = UUID("660e8400-e29b-41d4-a716-446655440000")
        description = "Test subscription"
        customer_id = "cust-1"
        product = mock_product

    mock_process_subscription = MagicMock()
    mock_process_subscription.subscription = GenericSubscription()
    process.process_subscriptions = [mock_process_subscription]

    config = ENTITY_CONFIG_REGISTRY[EntityType.PROCESS]
    extracted_fields = config.traverser.get_fields(entity=process, pk_name=config.pk_name, root_name=config.root_name)
    field_map = {field.path: field for field in extracted_fields}

    assert "process.subscriptions.0.customer_name" not in field_map
    assert "process.subscriptions.0.customer_abbreviation" not in field_map
    assert field_map["process.subscriptions.0.product_name"].value == "Test Product"
