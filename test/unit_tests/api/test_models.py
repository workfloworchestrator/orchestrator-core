from http import HTTPStatus
from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import BaseModel

from orchestrator.api.error_handling import ProblemDetailException
from orchestrator.api.models import cleanse_json, delete, parse_date_fields, save, transform_json, validate
from orchestrator.db import ProductTable, ResourceTypeTable


class TestModels(TestCase):
    def test_validate(self):
        with pytest.raises(ProblemDetailException) as excinfo:
            validate(ProductTable, {})

        assert excinfo.value.status_code == HTTPStatus.BAD_REQUEST
        assert (
            excinfo.value.detail == "Missing attributes 'name, description, product_type, tag, status' for ProductTable"
        )

        json_dict = {"resource_type": "some"}
        res = validate(ResourceTypeTable, json_dict)
        self.assertEqual(json_dict, res)

        with pytest.raises(ProblemDetailException) as excinfo:
            validate(ResourceTypeTable, json_dict, is_new_instance=False)

        assert excinfo.value.status_code == HTTPStatus.BAD_REQUEST
        assert excinfo.value.detail == "Missing attributes 'resource_type_id' for ResourceTypeTable"

    def test_transform_json(self):
        nested_body = {
            "name": "MSP",
            "description": "MSP",
            "product_type": "Port",
            "tag": "Port",
            "status": "active",
            "fixed_inputs": [{"name": "name", "value": "val"}, {"name": "name", "value": "val"}],
            "product_blocks": [{"name": "name", "description": "desc", "resource_types": [{"resource_type": "test"}]}],
        }

        nested_json_with_objects = transform_json(nested_body)
        product = ProductTable(**nested_json_with_objects)

        self.assertEqual("test", product.product_blocks[0].resource_types[0].resource_type)


# ---------------------------------------------------------------------------
# cleanse_json
# ---------------------------------------------------------------------------


def test_cleanse_json_removes_none_values():
    d = {"a": 1, "b": None, "c": "keep"}
    cleanse_json(d)
    assert d == {"a": 1, "c": "keep"}


def test_cleanse_json_removes_created_at():
    d = {"name": "foo", "created_at": "2024-01-01", "status": "active"}
    cleanse_json(d)
    assert "created_at" not in d
    assert d == {"name": "foo", "status": "active"}


def test_cleanse_json_recurses_into_lists():
    d = {
        "name": "product",
        "items": [
            {"x": 1, "created_at": "2024-01-01", "y": None},
            {"x": 2, "created_at": "2024-01-02"},
        ],
    }
    cleanse_json(d)
    assert d["items"][0] == {"x": 1}
    assert d["items"][1] == {"x": 2}


def test_cleanse_json_keeps_non_none_non_forbidden():
    d = {"end_date": "2025-01-01", "value": 42}
    cleanse_json(d)
    assert d == {"end_date": "2025-01-01", "value": 42}


def test_cleanse_json_empty_dict():
    d: dict = {}
    cleanse_json(d)
    assert d == {}


# ---------------------------------------------------------------------------
# parse_date_fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "val",
    [
        1_700_000_000_000.0,  # float millisecond timestamp
        1_700_000_000_000,  # int millisecond timestamp
    ],
)
def test_parse_date_fields_numeric_timestamp(val):
    from datetime import datetime

    d = {"end_date": val}
    parse_date_fields(d)
    assert isinstance(d["end_date"], datetime)


def test_parse_date_fields_iso_string_with_tz():
    d = {"end_date": "2024-06-15T12:00:00+00:00"}
    parse_date_fields(d)
    assert d["end_date"].tzinfo is not None


def test_parse_date_fields_iso_string_without_tz_raises():
    d = {"end_date": "2024-06-15T12:00:00"}
    with pytest.raises(AssertionError, match="timezone"):
        parse_date_fields(d)


def test_parse_date_fields_no_end_date_field_unchanged():
    d = {"name": "foo"}
    parse_date_fields(d)
    assert d == {"name": "foo"}


def test_parse_date_fields_recurses_into_lists():
    d = {
        "name": "root",
        "items": [
            {"end_date": "2024-01-01T00:00:00+00:00"},
        ],
    }
    parse_date_fields(d)
    assert d["items"][0]["end_date"].tzinfo is not None


# ---------------------------------------------------------------------------
# save / delete (mocked DB)
# ---------------------------------------------------------------------------


class _SampleModel(BaseModel):
    name: str
    value: int


def _make_db_cls():
    """Return a minimal fake DbBaseModel class with the __table__ interface."""
    mock_col_name = MagicMock()
    mock_col_name.nullable = False
    mock_col_name.server_default = None
    mock_col_name.primary_key = False

    mock_col_id = MagicMock()
    mock_col_id.nullable = False
    mock_col_id.server_default = None
    mock_col_id.primary_key = True

    table = MagicMock()
    table.columns._collection = [("name", mock_col_name), ("resource_type_id", mock_col_id)]

    cls = MagicMock()
    cls.__table__ = table
    cls.__name__ = "FakeTable"
    return cls


def test_save_calls_merge_and_commit():
    model = _SampleModel(name="test", value=1)

    with patch("orchestrator.api.models._merge") as mock_merge:
        save(ResourceTypeTable, model)
        mock_merge.assert_called_once()
        args = mock_merge.call_args[0]
        assert args[0] is ResourceTypeTable
        assert isinstance(args[1], dict)


def test_save_raises_on_merge_error():
    model = _SampleModel(name="test", value=1)

    with patch("orchestrator.api.models._merge", side_effect=RuntimeError("db error")):
        with pytest.raises(ProblemDetailException) as exc_info:
            save(ResourceTypeTable, model)
        assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_delete_raises_not_found_when_no_rows(generic_resource_type_1):
    missing_id = uuid4()
    with pytest.raises(ProblemDetailException) as exc_info:
        delete(ResourceTypeTable, missing_id)
    assert exc_info.value.status_code == HTTPStatus.NOT_FOUND


def test_delete_succeeds_when_row_exists(generic_resource_type_1):
    # Should not raise; the fixture adds exactly one ResourceTypeTable row
    delete(ResourceTypeTable, generic_resource_type_1.resource_type_id)
