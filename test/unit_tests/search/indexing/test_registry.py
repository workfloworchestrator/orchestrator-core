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

"""Tests for EntityConfig, ProcessConfig, WorkflowConfig, and ENTITY_CONFIG_REGISTRY.

Covers title resolution from fields, query construction with/without entity_id,
and registry completeness.
"""

from unittest.mock import MagicMock, call, patch

import pytest

from orchestrator.core.db import ProcessTable, ProductBlockTable, ResourceTypeTable, SubscriptionTable
from orchestrator.core.search.core.types import EntityType, ExtractedField, FieldType
from orchestrator.core.search.indexing.registry import (
    ENTITY_CONFIG_REGISTRY,
    EntityConfig,
    ProcessConfig,
    ProductBlockConfig,
    ResourceTypeConfig,
    WorkflowConfig,
)
from orchestrator.core.search.indexing.traverse import (
    ProcessTraverser,
    ProductBlockTraverser,
    ResourceTypeTraverser,
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
    config = ProcessConfig(
        entity_kind=EntityType.PROCESS,
        table=ProcessTable,
        traverser=MagicMock(),
        pk_name="process_id",
        root_name="process",
        title_paths=[],
    )

    select_result = MagicMock()
    options_result = MagicMock()
    select_result.options.return_value = options_result

    with (
        patch("sqlalchemy.select", return_value=select_result) as mock_select,
        patch("sqlalchemy.orm.selectinload") as mock_selectinload,
    ):
        result = config.get_all_query()

    mock_select.assert_called_once_with(ProcessTable)
    mock_selectinload.assert_has_calls(
        [call(ProcessTable.workflow), call(ProcessTable.process_subscriptions)], any_order=True
    )
    select_result.options.assert_called_once()
    assert result is options_result


# ---------------------------------------------------------------------------
# ProcessConfig, ProductBlockConfig, ResourceTypeConfig: get_all_query(entity_id=...)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("config_cls", "table", "pk_name", "root_name"),
    [
        pytest.param(ProcessConfig, ProcessTable, "process_id", "process", id="process"),
        pytest.param(ProductBlockConfig, ProductBlockTable, "product_block_id", "product_block", id="product_block"),
        pytest.param(ResourceTypeConfig, ResourceTypeTable, "resource_type_id", "resource_type", id="resource_type"),
    ],
)
def test_select_options_where_config_with_entity_id_applies_where(config_cls, table, pk_name, root_name):
    mock_table = MagicMock(spec=table)
    setattr(mock_table, pk_name, MagicMock())

    config = config_cls(
        entity_kind=EntityType.PROCESS,
        table=mock_table,
        traverser=MagicMock(),
        pk_name=pk_name,
        root_name=root_name,
        title_paths=[],
    )

    select_result = MagicMock()
    options_result = MagicMock()
    where_result = MagicMock()
    select_result.options.return_value = options_result
    options_result.where.return_value = where_result

    with patch("sqlalchemy.select", return_value=select_result), patch("sqlalchemy.orm.selectinload"):
        result = config.get_all_query(entity_id=VALID_UUID)

    options_result.where.assert_called_once()
    assert result is where_result


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


def test_registry_product_block_config_fields():
    config = ENTITY_CONFIG_REGISTRY[EntityType.METADATA_PRODUCT_BLOCK]
    assert config.pk_name == "product_block_id"
    assert config.root_name == "product_block"
    assert config.table is ProductBlockTable
    assert config.traverser is ProductBlockTraverser


def test_registry_resource_type_config_fields():
    config = ENTITY_CONFIG_REGISTRY[EntityType.METADATA_RESOURCE_TYPE]
    assert config.pk_name == "resource_type_id"
    assert config.root_name == "resource_type"
    assert config.table is ResourceTypeTable
    assert config.traverser is ResourceTypeTraverser


# ---------------------------------------------------------------------------
# ProductBlockConfig.get_all_query
# ---------------------------------------------------------------------------


def test_product_block_config_applies_selectinload_on_resource_types_and_in_use_by():
    config = ProductBlockConfig(
        entity_kind=EntityType.METADATA_PRODUCT_BLOCK,
        table=ProductBlockTable,
        traverser=MagicMock(),
        pk_name="product_block_id",
        root_name="product_block",
        title_paths=[],
    )

    select_result = MagicMock()
    options_result = MagicMock()
    select_result.options.return_value = options_result

    with (
        patch("sqlalchemy.select", return_value=select_result) as mock_select,
        patch("sqlalchemy.orm.selectinload") as mock_selectinload,
    ):
        result = config.get_all_query()

    mock_select.assert_called_once_with(ProductBlockTable)
    mock_selectinload.assert_has_calls(
        [call(ProductBlockTable.resource_types), call(ProductBlockTable.in_use_by_block_relations)],
        any_order=True,
    )
    select_result.options.assert_called_once()
    assert result is options_result


# ---------------------------------------------------------------------------
# ResourceTypeConfig.get_all_query
# ---------------------------------------------------------------------------


def test_resource_type_config_applies_selectinload_on_product_blocks():
    config = ResourceTypeConfig(
        entity_kind=EntityType.METADATA_RESOURCE_TYPE,
        table=ResourceTypeTable,
        traverser=MagicMock(),
        pk_name="resource_type_id",
        root_name="resource_type",
        title_paths=[],
    )

    select_result = MagicMock()
    options_result = MagicMock()
    selectinload_result = MagicMock()
    select_result.options.return_value = options_result

    with (
        patch("sqlalchemy.select", return_value=select_result) as mock_select,
        patch("sqlalchemy.orm.selectinload", return_value=selectinload_result) as mock_selectinload,
    ):
        result = config.get_all_query()

    mock_select.assert_called_once_with(ResourceTypeTable)
    mock_selectinload.assert_called_once_with(ResourceTypeTable.product_blocks)
    selectinload_result.noload.assert_called_once_with("*")
    select_result.options.assert_called_once_with(selectinload_result.noload.return_value)
    assert result is options_result
