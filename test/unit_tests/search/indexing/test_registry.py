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


class TestGetTitleFromFields:
    @pytest.mark.parametrize(
        "title_paths,fields,expected",
        [
            # Found: single path matches
            (
                ["subscription.description"],
                [ExtractedField(path="subscription.description", value="My Sub", value_type=FieldType.STRING)],
                "My Sub",
            ),
            # Fallback: first path not found, second path found
            (
                ["product.description", "product.name"],
                [
                    ExtractedField(path="product.name", value="FallbackName", value_type=FieldType.STRING),
                ],
                "FallbackName",
            ),
            # No match → "UNKNOWN"
            (
                ["subscription.description"],
                [ExtractedField(path="subscription.status", value="active", value_type=FieldType.STRING)],
                "UNKNOWN",
            ),
            # Empty value is falsy → "UNKNOWN"
            (
                ["subscription.description"],
                [ExtractedField(path="subscription.description", value="", value_type=FieldType.STRING)],
                "UNKNOWN",
            ),
            # Empty fields list → "UNKNOWN"
            (
                ["subscription.description"],
                [],
                "UNKNOWN",
            ),
        ],
    )
    def test_get_title_from_fields(self, title_paths: list[str], fields: list[ExtractedField], expected: str) -> None:
        config = _make_config(title_paths)
        assert config.get_title_from_fields(fields) == expected


# ---------------------------------------------------------------------------
# EntityConfig.get_all_query
# ---------------------------------------------------------------------------


class TestEntityConfigGetAllQuery:
    def test_without_entity_id_returns_base_query(self) -> None:
        mock_table = MagicMock()
        base_query = MagicMock()
        mock_table.query = base_query

        config: EntityConfig = EntityConfig(
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

    def test_with_entity_id_calls_filter_with_uuid(self) -> None:
        mock_table = MagicMock()
        base_query = MagicMock()
        filtered_query = MagicMock()
        pk_column = MagicMock()
        base_query.filter.return_value = filtered_query
        mock_table.query = base_query
        mock_table.subscription_id = pk_column

        config: EntityConfig = EntityConfig(
            entity_kind=EntityType.SUBSCRIPTION,
            table=mock_table,
            traverser=MagicMock(),
            pk_name="subscription_id",
            root_name="subscription",
            title_paths=[],
        )

        result = config.get_all_query(entity_id=VALID_UUID)

        assert result is filtered_query
        # Verify filter was called; the arg contains UUID(VALID_UUID) comparison expression
        base_query.filter.assert_called_once()


# ---------------------------------------------------------------------------
# ProcessConfig.get_all_query
# ---------------------------------------------------------------------------


class TestProcessConfigGetAllQuery:
    def test_applies_selectinload_on_workflow(self) -> None:
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

    def test_with_entity_id_applies_filter(self) -> None:
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


class TestWorkflowConfigGetAllQuery:
    def test_uses_select_not_query(self) -> None:
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

    def test_with_entity_id_calls_where(self) -> None:
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


class TestEntityConfigRegistry:
    def test_all_entity_types_present(self) -> None:
        assert set(ENTITY_CONFIG_REGISTRY.keys()) == set(EntityType)

    @pytest.mark.parametrize(
        "entity_type,expected_pk_name,expected_root_name,expected_table",
        [
            (EntityType.SUBSCRIPTION, "subscription_id", "subscription", SubscriptionTable),
        ],
    )
    def test_subscription_config_fields(
        self, entity_type: EntityType, expected_pk_name: str, expected_root_name: str, expected_table: type
    ) -> None:
        config = ENTITY_CONFIG_REGISTRY[entity_type]
        assert config.pk_name == expected_pk_name
        assert config.root_name == expected_root_name
        assert config.table is expected_table
        assert config.traverser is SubscriptionTraverser

    def test_process_config_is_process_config_instance(self) -> None:
        assert isinstance(ENTITY_CONFIG_REGISTRY[EntityType.PROCESS], ProcessConfig)

    def test_workflow_config_is_workflow_config_instance(self) -> None:
        assert isinstance(ENTITY_CONFIG_REGISTRY[EntityType.WORKFLOW], WorkflowConfig)

    def test_process_config_fields(self) -> None:
        config = ENTITY_CONFIG_REGISTRY[EntityType.PROCESS]
        assert config.pk_name == "process_id"
        assert config.root_name == "process"
        assert config.traverser is ProcessTraverser

    def test_workflow_config_fields(self) -> None:
        config = ENTITY_CONFIG_REGISTRY[EntityType.WORKFLOW]
        assert config.pk_name == "workflow_id"
        assert config.root_name == "workflow"
        assert config.traverser is WorkflowTraverser
