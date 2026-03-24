"""Tests for EntityConfig, ProcessConfig, WorkflowConfig, and ENTITY_CONFIG_REGISTRY.

Covers title resolution from fields, query construction with/without entity_id,
and registry completeness.
"""

from unittest.mock import MagicMock, patch

import pytest

from orchestrator.db import ProcessTable, SubscriptionTable
from orchestrator.search.core.types import EntityType, ExtractedField, FieldType
from orchestrator.search.indexing.registry import (
    ENTITY_CONFIG_REGISTRY,
    EntityConfig,
    ProcessConfig,
    WorkflowConfig,
)
from orchestrator.search.indexing.traverse import (
    ProcessTraverser,
    SubscriptionTraverser,
    WorkflowTraverser,
)

pytestmark = pytest.mark.search

VALID_UUID = "12345678-1234-1234-1234-123456789abc"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(title_paths: list[str]) -> EntityConfig:
    """Return a minimal EntityConfig with the given title_paths using a MagicMock table."""
    mock_table = MagicMock()
    mock_table.query = MagicMock()
    return EntityConfig(
        entity_kind=EntityType.SUBSCRIPTION,
        table=mock_table,
        traverser=MagicMock(),
        pk_name="subscription_id",
        root_name="subscription",
        title_paths=title_paths,
    )


# ---------------------------------------------------------------------------
# EntityConfig.get_title_from_fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title_paths", "fields", "expected"),
    [
        pytest.param(
            ["subscription.description"],
            [ExtractedField(path="subscription.description", value="My Sub", value_type=FieldType.STRING)],
            "My Sub",
            id="single_path_match",
        ),
        pytest.param(
            ["product.description", "product.name"],
            [ExtractedField(path="product.name", value="FallbackName", value_type=FieldType.STRING)],
            "FallbackName",
            id="fallback_to_second_path",
        ),
        pytest.param(
            ["subscription.description"],
            [ExtractedField(path="subscription.status", value="active", value_type=FieldType.STRING)],
            "UNKNOWN",
            id="no_match",
        ),
        pytest.param(
            ["subscription.description"],
            [ExtractedField(path="subscription.description", value="", value_type=FieldType.STRING)],
            "UNKNOWN",
            id="empty_value_is_unknown",
        ),
        pytest.param(
            ["subscription.description"],
            [],
            "UNKNOWN",
            id="empty_fields_list",
        ),
    ],
)
def test_get_title_from_fields(title_paths, fields, expected):
    config = _make_config(title_paths)
    assert config.get_title_from_fields(fields) == expected


# ---------------------------------------------------------------------------
# EntityConfig.get_all_query
# ---------------------------------------------------------------------------


def test_entity_config_get_all_query_without_entity_id():
    mock_table = MagicMock()
    base_query = MagicMock()
    mock_table.query = base_query

    config = EntityConfig(
        entity_kind=EntityType.SUBSCRIPTION,
        table=mock_table,
        traverser=MagicMock(),
        pk_name="subscription_id",
        root_name="subscription",
        title_paths=[],
    )

    result = config.get_all_query()

    assert result is base_query
    base_query.filter.assert_not_called()


def test_entity_config_get_all_query_with_entity_id():
    mock_table = MagicMock()
    base_query = MagicMock()
    filtered_query = MagicMock()
    pk_column = MagicMock()
    base_query.filter.return_value = filtered_query
    mock_table.query = base_query
    mock_table.subscription_id = pk_column

    config = EntityConfig(
        entity_kind=EntityType.SUBSCRIPTION,
        table=mock_table,
        traverser=MagicMock(),
        pk_name="subscription_id",
        root_name="subscription",
        title_paths=[],
    )

    result = config.get_all_query(entity_id=VALID_UUID)

    assert result is filtered_query
    base_query.filter.assert_called_once()


# ---------------------------------------------------------------------------
# ProcessConfig.get_all_query
# ---------------------------------------------------------------------------


def test_process_config_applies_selectinload_on_workflow():
    mock_table = MagicMock(spec=ProcessTable)
    base_query = MagicMock()
    options_query = MagicMock()
    mock_table.query = base_query
    base_query.options.return_value = options_query

    config = ProcessConfig(
        entity_kind=EntityType.PROCESS,
        table=mock_table,
        traverser=MagicMock(),
        pk_name="process_id",
        root_name="process",
        title_paths=[],
    )

    with patch("sqlalchemy.orm.selectinload") as mock_selectinload:
        result = config.get_all_query()

    mock_selectinload.assert_called_once_with(ProcessTable.workflow)
    base_query.options.assert_called_once()
    assert result is options_query


def test_process_config_with_entity_id_applies_filter():
    mock_table = MagicMock(spec=ProcessTable)
    base_query = MagicMock()
    options_query = MagicMock()
    filtered_query = MagicMock()
    mock_table.query = base_query
    base_query.options.return_value = options_query
    options_query.filter.return_value = filtered_query

    config = ProcessConfig(
        entity_kind=EntityType.PROCESS,
        table=mock_table,
        traverser=MagicMock(),
        pk_name="process_id",
        root_name="process",
        title_paths=[],
    )

    with patch("sqlalchemy.orm.selectinload"):
        result = config.get_all_query(entity_id=VALID_UUID)

    options_query.filter.assert_called_once()
    assert result is filtered_query


# ---------------------------------------------------------------------------
# WorkflowConfig.get_all_query
# ---------------------------------------------------------------------------


def test_workflow_config_uses_select_not_query():
    mock_table = MagicMock()
    select_result = MagicMock()
    mock_table.select.return_value = select_result

    config = WorkflowConfig(
        entity_kind=EntityType.WORKFLOW,
        table=mock_table,
        traverser=MagicMock(),
        pk_name="workflow_id",
        root_name="workflow",
        title_paths=[],
    )

    result = config.get_all_query()

    mock_table.select.assert_called_once()
    assert result is select_result


def test_workflow_config_with_entity_id_calls_where():
    mock_table = MagicMock()
    select_result = MagicMock()
    where_result = MagicMock()
    mock_table.select.return_value = select_result
    select_result.where.return_value = where_result

    config = WorkflowConfig(
        entity_kind=EntityType.WORKFLOW,
        table=mock_table,
        traverser=MagicMock(),
        pk_name="workflow_id",
        root_name="workflow",
        title_paths=[],
    )

    result = config.get_all_query(entity_id=VALID_UUID)

    select_result.where.assert_called_once()
    assert result is where_result


# ---------------------------------------------------------------------------
# ENTITY_CONFIG_REGISTRY
# ---------------------------------------------------------------------------


def test_registry_all_entity_types_present():
    assert set(ENTITY_CONFIG_REGISTRY.keys()) == set(EntityType)


def test_registry_subscription_config_fields():
    config = ENTITY_CONFIG_REGISTRY[EntityType.SUBSCRIPTION]
    assert config.pk_name == "subscription_id"
    assert config.root_name == "subscription"
    assert config.table is SubscriptionTable
    assert config.traverser is SubscriptionTraverser


def test_registry_process_config_fields():
    config = ENTITY_CONFIG_REGISTRY[EntityType.PROCESS]
    assert config.pk_name == "process_id"
    assert config.root_name == "process"
    assert config.traverser is ProcessTraverser


def test_registry_workflow_config_fields():
    config = ENTITY_CONFIG_REGISTRY[EntityType.WORKFLOW]
    assert config.pk_name == "workflow_id"
    assert config.root_name == "workflow"
    assert config.traverser is WorkflowTraverser
