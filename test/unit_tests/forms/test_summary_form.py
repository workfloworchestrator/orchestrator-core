# Copyright 2026 SURF, GÉANT.
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

"""Tests for the summary form generator.

Covers translation lookups, field filtering/formatting, table generation (single, before/after,
single-column), form assembly, and the small summary formatters.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from orchestrator.core.forms.summary_form import summary_form as sf
from orchestrator.core.forms.summary_form.summary_form import (
    TABLE_NUMBER_FIELD,
    _filter_summary_fields,
    _generate_before_after_tables,
    _generate_single_column_tables,
    _get_column_values,
    _get_summary_labels,
    _make_summary_table_header,
    _table_fields,
    _table_number,
    _validate_uniform_old_data,
    base_summary,
    create_table,
    generate_summary_form,
    subscription_summary_fields,
)

# --- _filter_summary_fields ---


def test_filter_summary_fields_excludes_labels_dividers_form_info_and_action_choices():
    data = {
        "a": 1,
        "label_x": 1,
        "divider_1": None,
        "form_info_x": 1,
        "action_choice_x": 1,
        TABLE_NUMBER_FIELD: 1,
        "b": 2,
    }

    assert list(_filter_summary_fields(data, {})) == ["a", "b"]


def test_filter_summary_fields_with_custom_exclude():
    data = {"a": 1, "b": 2}

    assert list(_filter_summary_fields(data, {"exclude": {"b"}})) == ["a"]


# --- _get_summary_labels / _get_column_values ---


def test_get_summary_labels_uses_translation_by_default():
    data = {"subscription_id": "id-1"}

    assert _get_summary_labels(data, {}) == ["Subscription"]


def test_get_summary_labels_uses_formatter_and_can_expand_to_multiple_labels():
    def fmt(value):
        yield "Custom Label 1", value[0]
        yield "Custom Label 2", value[1]

    data = {"pair": (1, 2), "plain": "x"}
    options = {"formatter": {"pair": fmt}}

    assert _get_summary_labels(data, options) == ["Custom Label 1", "Custom Label 2", "plain"]


@pytest.mark.parametrize(
    "field_value,expected",
    [
        (None, ""),
        ([], ""),
        ({}, ""),
        ("x", "x"),
        (0, "0"),
        (["a", "b"], "['a', 'b']"),
    ],
)
def test_get_column_values_default_formatting(field_value, expected):
    data = {"field": field_value}

    assert _get_column_values(data, {}) == [expected]


def test_get_column_values_uses_formatter():
    def fmt(value):
        yield "Custom Label 1", value[0]
        yield "Custom Label 2", value[1]

    data = {"pair": (1, 2)}
    options = {"formatter": {"pair": fmt}}

    assert _get_column_values(data, options) == ["1", "2"]


# --- create_table ---


def test_create_table_builds_labels_columns_and_default_headers():
    options = {"name": "product_summary", "data": [({"a": 1, "b": 2}, None), ({"a": 3, "b": 4}, None)]}

    table_type = create_table(options, show_headers=True)

    assert table_type.__origin__.data == {
        "labels": ["a", "b"],
        "columns": [["1", "2"], ["3", "4"]],
        "headers": ["1", "2"],
    }


def test_create_table_show_headers_false_yields_no_headers():
    options = {"name": "product_summary", "data": [({"a": 1}, None)]}

    table_type = create_table(options, show_headers=False)

    assert table_type.__origin__.data["headers"] == []


def test_create_table_custom_header_callable():
    options = {"name": "endpoints", "data": [({"a": 1}, None)], "header": lambda index: f"Endpoint {index}"}

    table_type = create_table(options)

    assert table_type.__origin__.data["headers"] == ["Endpoint 1"]


# --- _table_number ---


@pytest.mark.parametrize(
    "table_data,default,expected",
    [
        ({"endpoint_nr": 5}, 99, 6),
        ({"endpoint_nr": 0}, 99, 1),
        ({TABLE_NUMBER_FIELD: 7}, 99, 7),
        ({"endpoint_nr": 0, TABLE_NUMBER_FIELD: 7}, 99, 1),
        ({}, 99, 99),
    ],
)
def test_table_number(table_data, default, expected):
    assert _table_number(table_data=table_data, default=default) == expected


# --- _make_summary_table_header ---


def test_make_summary_table_header_uses_custom_header_fn():
    options = {"header": lambda index: f"H{index}"}

    assert _make_summary_table_header(options, 1, "Default") == "H1"


def test_make_summary_table_header_falls_back_to_default():
    assert _make_summary_table_header({}, 1, "Default") == "Default"


# --- _generate_before_after_tables ---


def test_generate_before_after_tables_numbers_each_table():
    options = {"name": "endpoints", "data": [({"a": 1}, {"a": 0}), ({"a": 2}, {"a": 1})]}

    names = [name for name, _ in _generate_before_after_tables(options)]

    assert names == ["endpoints 1", "endpoints 2"]


def test_generate_before_after_tables_product_summary_has_no_numbering():
    options = {"name": "product_summary", "data": [({"a": 1}, {"a": 0})]}

    names = [name for name, _ in _generate_before_after_tables(options)]

    assert names == ["product_summary"]


def test_generate_before_after_tables_uses_before_after_headers_by_default():
    options = {"name": "endpoints", "data": [({"a": 1}, {"a": 0})]}

    _, (table_type, _) = next(_generate_before_after_tables(options))

    assert table_type.__origin__.data["headers"] == ["Before", "After"]
    assert table_type.__origin__.data["columns"] == [["0"], ["1"]]


# --- _generate_single_column_tables ---


def test_generate_single_column_tables_numbers_each_table():
    options = {"name": "items", "data": [({"a": 1}, None), ({"a": 2}, None)]}

    names = [name for name, _ in _generate_single_column_tables(options)]

    assert names == ["items 1", "items 2"]


def test_generate_single_column_tables_uses_table_number_field_for_naming():
    options = {"name": "items", "data": [({"a": 1, TABLE_NUMBER_FIELD: 5}, None)]}

    names = [name for name, _ in _generate_single_column_tables(options)]

    assert names == ["items 5"]


# --- _validate_uniform_old_data ---


@pytest.mark.parametrize(
    "data",
    [
        [({"a": 1}, {"a": 0}), ({"a": 2}, {"a": 1})],
        [({"a": 1}, None), ({"a": 2}, None)],
        [],
    ],
)
def test_validate_uniform_old_data_allows_consistent_data(data):
    _validate_uniform_old_data(data)


@pytest.mark.parametrize(
    "data",
    [
        [({"a": 1}, None), ({"a": 2}, {"a": 1})],
        [({"a": 1}, {"a": 0}), ({"a": 2}, None)],
    ],
)
def test_validate_uniform_old_data_rejects_mixed_old_data(data):
    with pytest.raises(ValueError, match="Inconsistent table data"):
        _validate_uniform_old_data(data)


# --- _table_fields ---


def test_table_fields_dispatches_before_after_when_old_data_present():
    options = {"name": "endpoints", "data": [({"a": 1}, {"a": 0})]}

    fields = dict(_table_fields(options, 1))

    assert set(fields) == {"divider_2", "endpoints 1"}


def test_table_fields_raises_on_mixed_old_data():
    options = {"name": "endpoints", "data": [({"a": 1}, None), ({"a": 2}, {"a": 1})]}

    with pytest.raises(ValueError, match="Inconsistent table data"):
        dict(_table_fields(options, 1))


def test_table_fields_dispatches_single_column_when_configured():
    options = {"name": "items", "data": [({"a": 1}, None)], "single_column": True}

    fields = dict(_table_fields(options, 1))

    assert set(fields) == {"divider_2", "items 1"}


def test_table_fields_dispatches_plain_table_by_default():
    options = {"name": "plain", "data": [({"a": 1}, None)]}

    fields = dict(_table_fields(options, 0))

    assert set(fields) == {"divider_1", "plain"}


def test_table_fields_uses_default_empty_message_when_no_data():
    options = {"name": "empty_table"}

    fields = dict(_table_fields(options, 1))

    assert fields["empty_table"][1] == "no data"


def test_table_fields_uses_custom_empty_message():
    options = {"name": "empty_table", "empty_message": "Nothing here"}

    fields = dict(_table_fields(options, 1))

    assert fields["empty_table"][1] == "Nothing here"


# --- generate_summary_form ---


def test_generate_summary_form_assembles_all_field_groups_in_order():
    options = {
        "product_name": "My Product",
        "product": {"name": "product_summary", "data": [({"a": 1}, None)]},
        "after_product": {"note": (str, "hey")},
    }

    model = next(generate_summary_form(options))

    assert model.model_config["title"] == "My Product Summary"
    assert list(model.model_fields.keys()) == ["divider_1", "product_summary", "note"]


def test_generate_summary_form_without_optional_sections():
    options = {"product_name": "My Product", "product": {"name": "product_summary", "data": [({"a": 1}, None)]}}

    model = next(generate_summary_form(options))

    assert list(model.model_fields.keys()) == ["divider_1", "product_summary"]


# --- base_summary ---


def test_base_summary_wraps_single_product_row():
    model = next(base_summary("My Product", {"a": 1}, {"a": 0}))

    assert model.model_config["title"] == "My Product Summary"
    assert list(model.model_fields.keys()) == ["divider_1", "product_summary"]

    schema = model.model_json_schema()
    product_summary_data = schema["properties"]["product_summary"]["uniforms"]["data"]
    assert product_summary_data["headers"] == ["Before", "After"]
    assert product_summary_data["columns"] == [["0"], ["1"]]


def test_base_summary_includes_extra_tables():
    model = next(
        base_summary(
            "My Product",
            {"a": 1},
            tables=[{"name": "note", "data": [({"x": 1}, None)]}],
        )
    )

    assert list(model.model_fields.keys()) == ["divider_1", "product_summary", "divider_2", "note"]

    schema = model.model_json_schema()
    product_summary_data = schema["properties"]["note"]["uniforms"]["data"]
    assert product_summary_data["labels"] == ["x"]


# --- subscription_summary_fields ---


@pytest.fixture
def mock_subscription():
    sub = MagicMock()
    sub.subscription_id = uuid4()
    sub.description = "some description"
    sub._product_block_fields_ = {"ip_block": None}
    return sub


def test_subscription_summary_fields_includes_block_title(mock_subscription):
    mock_subscription.ip_block.title = "Block title"

    with patch.object(sf, "SubscriptionModel") as mock_model:
        mock_model.from_subscription.return_value = mock_subscription

        result = list(subscription_summary_fields(mock_subscription.subscription_id))

    assert result == [
        ("Subscription", str(mock_subscription.subscription_id)),
        ("description", "some description"),
        ("title", "Block title"),
    ]


def test_subscription_summary_fields_defaults_title_when_block_has_none(mock_subscription):
    del mock_subscription.ip_block.title

    with patch.object(sf, "SubscriptionModel") as mock_model:
        mock_model.from_subscription.return_value = mock_subscription

        result = list(subscription_summary_fields(mock_subscription.subscription_id))

    assert result[-1] == ("title", "-")
