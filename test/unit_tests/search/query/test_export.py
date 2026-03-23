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

from datetime import date, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from orchestrator.search.core.types import EntityType
from orchestrator.search.query.export import (
    fetch_export_data,
    fetch_process_export_data,
    fetch_product_export_data,
    fetch_subscription_export_data,
    fetch_workflow_export_data,
)

pytestmark = pytest.mark.search

# =============================================================================
# Constants
# =============================================================================

SUBSCRIPTION_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
PRODUCT_ID = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
PROCESS_ID = "c3d4e5f6-a7b8-9012-cdef-123456789012"
WORKFLOW_ID = "d4e5f6a7-b8c9-0123-def0-234567890123"
CUSTOMER_ID = UUID("e5f6a7b8-c9d0-1234-ef01-345678901234")

_DEFAULT_SUBSCRIPTION_UUID = UUID(SUBSCRIPTION_ID)
_DEFAULT_PRODUCT_UUID = UUID(PRODUCT_ID)
_DEFAULT_PROCESS_UUID = UUID(PROCESS_ID)
_DEFAULT_WORKFLOW_UUID = UUID(WORKFLOW_ID)

SAMPLE_DATE = date(2024, 1, 15)
SAMPLE_DATETIME = datetime(2024, 1, 15, 10, 30, 0)

# =============================================================================
# Helpers
# =============================================================================


def _make_subscription_row(
    *,
    subscription_id: UUID = _DEFAULT_SUBSCRIPTION_UUID,
    description: str = "Test subscription",
    status: str = "active",
    insync: bool = True,
    start_date: date | None = SAMPLE_DATE,
    end_date: date | None = SAMPLE_DATE,
    note: str | None = "A note",
    customer_id: UUID = CUSTOMER_ID,
    product_name: str = "TestProduct",
    tag: str = "TP",
    product_type: str = "IP",
) -> MagicMock:
    row = MagicMock()
    row.subscription_id = subscription_id
    row.description = description
    row.status = status
    row.insync = insync
    row.start_date = start_date
    row.end_date = end_date
    row.note = note
    row.customer_id = customer_id
    row.product_name = product_name
    row.tag = tag
    row.product_type = product_type
    return row


def _make_workflow(
    *,
    name: str = "create_subscription",
    description: str = "Creates a subscription",
    created_at: datetime | None = SAMPLE_DATETIME,
    products: list | None = None,
) -> MagicMock:
    wf = MagicMock()
    wf.name = name
    wf.description = description
    wf.created_at = created_at
    wf.products = products if products is not None else []
    return wf


def _make_product(
    *,
    product_id: UUID = _DEFAULT_PRODUCT_UUID,
    name: str = "TestProduct",
    product_type: str = "IP",
    tag: str = "TP",
    description: str = "A product",
    status: str = "active",
    created_at: datetime | None = SAMPLE_DATETIME,
) -> MagicMock:
    p = MagicMock()
    p.product_id = product_id
    p.name = name
    p.product_type = product_type
    p.tag = tag
    p.description = description
    p.status = status
    p.created_at = created_at
    return p


_SENTINEL = object()


def _make_process(
    *,
    process_id: UUID = _DEFAULT_PROCESS_UUID,
    workflow: MagicMock | None = _SENTINEL,  # type: ignore[assignment]
    workflow_id: UUID = _DEFAULT_WORKFLOW_UUID,
    last_status: str = "completed",
    is_task: bool = False,
    created_by: str = "user@example.com",
    started_at: datetime | None = SAMPLE_DATETIME,
    last_modified_at: datetime | None = SAMPLE_DATETIME,
    last_step: str = "done",
) -> MagicMock:
    if workflow is _SENTINEL:
        workflow = MagicMock()
        workflow.name = "create_subscription"
    p = MagicMock()
    p.process_id = process_id
    p.workflow = workflow
    p.workflow_id = workflow_id
    p.last_status = last_status
    p.is_task = is_task
    p.created_by = created_by
    p.started_at = started_at
    p.last_modified_at = last_modified_at
    p.last_step = last_step
    return p


# =============================================================================
# TestFetchSubscriptionExportData
# =============================================================================


class TestFetchSubscriptionExportData:
    """Tests for fetch_subscription_export_data."""

    def test_single_row_all_fields_populated(self) -> None:
        """A single row with all fields set returns the expected dict."""
        row = _make_subscription_row()
        mock_result = MagicMock()
        mock_result.all.return_value = [row]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.execute.return_value = mock_result
            result = fetch_subscription_export_data([SUBSCRIPTION_ID])

        assert len(result) == 1
        record = result[0]
        assert record["subscription_id"] == SUBSCRIPTION_ID
        assert record["description"] == "Test subscription"
        assert record["status"] == "active"
        assert record["insync"] is True
        assert record["start_date"] == SAMPLE_DATE.isoformat()
        assert record["end_date"] == SAMPLE_DATE.isoformat()
        assert record["note"] == "A note"
        assert record["customer_id"] == CUSTOMER_ID
        assert record["product_name"] == "TestProduct"
        assert record["tag"] == "TP"
        assert record["product_type"] == "IP"

    def test_none_date_fields_returned_as_none(self) -> None:
        """start_date and end_date of None produce None in the output dict."""
        row = _make_subscription_row(start_date=None, end_date=None)
        mock_result = MagicMock()
        mock_result.all.return_value = [row]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.execute.return_value = mock_result
            result = fetch_subscription_export_data([SUBSCRIPTION_ID])

        assert result[0]["start_date"] is None
        assert result[0]["end_date"] is None

    def test_subscription_id_cast_to_string(self) -> None:
        """subscription_id UUID is converted to a plain string."""
        row = _make_subscription_row(subscription_id=UUID(SUBSCRIPTION_ID))
        mock_result = MagicMock()
        mock_result.all.return_value = [row]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.execute.return_value = mock_result
            result = fetch_subscription_export_data([SUBSCRIPTION_ID])

        assert isinstance(result[0]["subscription_id"], str)
        assert result[0]["subscription_id"] == SUBSCRIPTION_ID

    def test_empty_entity_ids_returns_empty_list(self) -> None:
        """Empty entity_ids list produces an empty result."""
        mock_result = MagicMock()
        mock_result.all.return_value = []

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.execute.return_value = mock_result
            result = fetch_subscription_export_data([])

        assert result == []

    def test_multiple_rows_returned(self) -> None:
        """Multiple rows each produce their own dict in the output list."""
        id2 = "f6a7b8c9-d0e1-2345-f012-456789012345"
        row1 = _make_subscription_row(subscription_id=UUID(SUBSCRIPTION_ID), description="First")
        row2 = _make_subscription_row(subscription_id=UUID(id2), description="Second")
        mock_result = MagicMock()
        mock_result.all.return_value = [row1, row2]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.execute.return_value = mock_result
            result = fetch_subscription_export_data([SUBSCRIPTION_ID, id2])

        assert len(result) == 2
        assert result[0]["description"] == "First"
        assert result[1]["description"] == "Second"


# =============================================================================
# TestFetchWorkflowExportData
# =============================================================================


class TestFetchWorkflowExportData:
    """Tests for fetch_workflow_export_data."""

    def test_single_workflow_no_products(self) -> None:
        """A workflow with no products returns empty comma-joined fields."""
        wf = _make_workflow(products=[])
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [wf]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_workflow_export_data(["create_subscription"])

        assert len(result) == 1
        record = result[0]
        assert record["name"] == "create_subscription"
        assert record["description"] == "Creates a subscription"
        assert record["created_at"] == SAMPLE_DATETIME.isoformat()
        assert record["product_names"] == ""
        assert record["product_ids"] == ""
        assert record["product_types"] == ""

    def test_workflow_with_multiple_products(self) -> None:
        """Products are comma-joined in name, id, and type fields."""
        p1 = _make_product(product_id=UUID(PRODUCT_ID), name="ProdA", product_type="TypeA")
        p2_id = "b2c3d4e5-f6a7-8901-bcde-f12345678902"
        p2 = _make_product(product_id=UUID(p2_id), name="ProdB", product_type="TypeB")
        wf = _make_workflow(products=[p1, p2])
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [wf]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_workflow_export_data(["create_subscription"])

        record = result[0]
        assert record["product_names"] == "ProdA, ProdB"
        assert record["product_ids"] == f"{PRODUCT_ID}, {p2_id}"
        assert record["product_types"] == "TypeA, TypeB"

    def test_none_created_at_returns_none(self) -> None:
        """created_at=None produces None in the output dict."""
        wf = _make_workflow(created_at=None)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [wf]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_workflow_export_data(["create_subscription"])

        assert result[0]["created_at"] is None

    def test_empty_entity_ids_returns_empty_list(self) -> None:
        """Empty entity_ids list produces an empty result."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_workflow_export_data([])

        assert result == []

    def test_single_product_no_trailing_comma(self) -> None:
        """A workflow with exactly one product has no trailing separator."""
        p = _make_product(product_id=UUID(PRODUCT_ID), name="Solo", product_type="SoloType")
        wf = _make_workflow(products=[p])
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [wf]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_workflow_export_data(["create_subscription"])

        assert result[0]["product_names"] == "Solo"
        assert result[0]["product_ids"] == PRODUCT_ID
        assert result[0]["product_types"] == "SoloType"


# =============================================================================
# TestFetchProductExportData
# =============================================================================


class TestFetchProductExportData:
    """Tests for fetch_product_export_data."""

    def test_single_product_all_fields_populated(self) -> None:
        """A single product with all fields set returns the expected dict."""
        p = _make_product()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [p]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_product_export_data([PRODUCT_ID])

        assert len(result) == 1
        record = result[0]
        assert record["product_id"] == PRODUCT_ID
        assert record["name"] == "TestProduct"
        assert record["product_type"] == "IP"
        assert record["tag"] == "TP"
        assert record["description"] == "A product"
        assert record["status"] == "active"
        assert record["created_at"] == SAMPLE_DATETIME.isoformat()

    def test_none_created_at_returns_none(self) -> None:
        """created_at=None produces None in the output dict."""
        p = _make_product(created_at=None)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [p]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_product_export_data([PRODUCT_ID])

        assert result[0]["created_at"] is None

    def test_product_id_cast_to_string(self) -> None:
        """product_id UUID is converted to a plain string."""
        p = _make_product(product_id=UUID(PRODUCT_ID))
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [p]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_product_export_data([PRODUCT_ID])

        assert isinstance(result[0]["product_id"], str)
        assert result[0]["product_id"] == PRODUCT_ID

    def test_empty_entity_ids_returns_empty_list(self) -> None:
        """Empty entity_ids list produces an empty result."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_product_export_data([])

        assert result == []

    def test_multiple_products_returned(self) -> None:
        """Multiple products each produce their own dict."""
        id2 = "b2c3d4e5-f6a7-8901-bcde-f12345678902"
        p1 = _make_product(product_id=UUID(PRODUCT_ID), name="First")
        p2 = _make_product(product_id=UUID(id2), name="Second")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [p1, p2]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_product_export_data([PRODUCT_ID, id2])

        assert len(result) == 2
        assert result[0]["name"] == "First"
        assert result[1]["name"] == "Second"


# =============================================================================
# TestFetchProcessExportData
# =============================================================================


class TestFetchProcessExportData:
    """Tests for fetch_process_export_data."""

    def test_single_process_all_fields_populated(self) -> None:
        """A single process with all fields set returns the expected dict."""
        proc = _make_process()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [proc]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_process_export_data([PROCESS_ID])

        assert len(result) == 1
        record = result[0]
        assert record["process_id"] == PROCESS_ID
        assert record["workflow_name"] == "create_subscription"
        assert record["workflow_id"] == WORKFLOW_ID
        assert record["last_status"] == "completed"
        assert record["is_task"] is False
        assert record["created_by"] == "user@example.com"
        assert record["started_at"] == SAMPLE_DATETIME.isoformat()
        assert record["last_modified_at"] == SAMPLE_DATETIME.isoformat()
        assert record["last_step"] == "done"

    def test_workflow_none_returns_none_for_workflow_name(self) -> None:
        """When process.workflow is None, workflow_name is None in the output."""
        proc = _make_process(workflow=None)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [proc]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_process_export_data([PROCESS_ID])

        assert result[0]["workflow_name"] is None

    def test_none_date_fields_returned_as_none(self) -> None:
        """started_at and last_modified_at of None produce None in the output dict."""
        proc = _make_process(started_at=None, last_modified_at=None)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [proc]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_process_export_data([PROCESS_ID])

        assert result[0]["started_at"] is None
        assert result[0]["last_modified_at"] is None

    def test_process_id_cast_to_string(self) -> None:
        """process_id UUID is converted to a plain string."""
        proc = _make_process(process_id=UUID(PROCESS_ID))
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [proc]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_process_export_data([PROCESS_ID])

        assert isinstance(result[0]["process_id"], str)
        assert result[0]["process_id"] == PROCESS_ID

    def test_empty_entity_ids_returns_empty_list(self) -> None:
        """Empty entity_ids list produces an empty result."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_process_export_data([])

        assert result == []

    def test_is_task_true_preserved(self) -> None:
        """is_task=True is correctly propagated to the output dict."""
        proc = _make_process(is_task=True)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [proc]

        with patch("orchestrator.search.query.export.db") as mock_db:
            mock_db.session.scalars.return_value = mock_scalars
            result = fetch_process_export_data([PROCESS_ID])

        assert result[0]["is_task"] is True


# =============================================================================
# TestFetchExportData
# =============================================================================


class TestFetchExportData:
    """Tests for the fetch_export_data dispatch function."""

    @pytest.mark.parametrize(
        "entity_type,patch_target",
        [
            (EntityType.SUBSCRIPTION, "orchestrator.search.query.export.fetch_subscription_export_data"),
            (EntityType.WORKFLOW, "orchestrator.search.query.export.fetch_workflow_export_data"),
            (EntityType.PRODUCT, "orchestrator.search.query.export.fetch_product_export_data"),
            (EntityType.PROCESS, "orchestrator.search.query.export.fetch_process_export_data"),
        ],
        ids=["subscription", "workflow", "product", "process"],
    )
    def test_dispatches_to_correct_fetch_function(self, entity_type: EntityType, patch_target: str) -> None:
        """fetch_export_data calls the correct underlying fetch function for each entity type."""
        entity_ids = ["id-1", "id-2"]
        expected = [{"key": "value"}]

        with patch(patch_target, return_value=expected) as mock_fetch:
            result = fetch_export_data(entity_type, entity_ids)

        mock_fetch.assert_called_once_with(entity_ids)
        assert result == expected

    def test_unsupported_entity_type_raises_value_error(self) -> None:
        """An entity type not handled by the match statement raises ValueError."""
        fake_type = MagicMock(spec=EntityType)
        fake_type.__class__ = EntityType  # type: ignore[assignment]

        with pytest.raises(ValueError, match="Unsupported entity type"):
            fetch_export_data(fake_type, ["some-id"])
