# Copyright 2026 SURF.
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

import itertools
from collections.abc import Callable, Generator, Iterable, Iterator, Sequence
from itertools import chain
from typing import Any, TypedDict
from uuid import UUID

import structlog
from more_itertools import first
from pydantic import ConfigDict, create_model

from orchestrator.core.domain import SubscriptionModel
from orchestrator.core.forms import FormPage, SubmitFormPage
from orchestrator.core.forms.validators import Divider, MigrationSummary, migration_summary
from orchestrator.core.services.translations import generate_translations
from pydantic_forms.types import SummaryData, UUIDstr
from pydantic_forms.validators import read_only_field

logger = structlog.get_logger(__name__)

RowGenerator = Generator[tuple[str, str], None, None]
FormFieldGenerator = Generator[tuple[str, tuple], None, None]
Formatter = Callable[[Any], RowGenerator]
FormPageGenerator = Generator[type[FormPage], None, None]
TableData = Sequence[tuple[dict, dict | None]]

_TRANSLATIONS = generate_translations(language="en-GB")
_FIELD_TRANSLATIONS: dict = _TRANSLATIONS["forms"]["fields"]  # type: ignore
_SUMMARY_TRANSLATIONS: dict = _FIELD_TRANSLATIONS["summary"]

MERGED_TRANSLATIONS = _FIELD_TRANSLATIONS | _SUMMARY_TRANSLATIONS


TABLE_NUMBER_FIELD = "__table_number"
PRODUCT_SUMMARY_TABLE_NAME = "product_summary"

DEFAULT_EXCLUDE_FIELDS = {
    TABLE_NUMBER_FIELD,
}


class BaseOptions(TypedDict, total=False):
    exclude: set[str]
    formatter: dict[str, Formatter]


class TableOptions(BaseOptions, total=False):
    name: str
    header: Callable[[Any], str]
    data: TableData
    empty_message: str
    single_column: bool  # Set True to spread columns out over separate tables


class SummaryOptions(TypedDict, total=False):
    product_name: str
    product: TableOptions
    after_product: dict[str, tuple]
    tables: Sequence[TableOptions]


def get_field_translation(key: str, default: str = "") -> str:
    """Translate a form field key to its display label.

    Use this for labels shared with the regular (non-summary) form, e.g. "subscription_id" or "description".
    Falls back to `default`, or to `key` itself, when no translation is found.

    >>> get_field_translation("subscription_id")
    'Subscription'
    >>> get_field_translation("some_unknown_field")
    'some_unknown_field'
    >>> get_field_translation("some_unknown_field", "My Default")
    'My Default'
    """
    return _FIELD_TRANSLATIONS.get(key, default if default else key)


def get_summary_translation(key: str, default: str = "") -> str:
    """Translate a summary field key to its display label.

    Like `get_field_translation`, but also checks summary-specific translation overrides
    (forms.fields.summary.<key>) before falling back to the shared field translations.

    >>> get_summary_translation("subscription_id")
    'Subscription'
    >>> get_summary_translation("some_unknown_field")
    'some_unknown_field'
    """
    return MERGED_TRANSLATIONS.get(key, default if default else key)


def _filter_summary_fields(data: dict, options: BaseOptions) -> Generator[str, None, None]:
    """Yield the field names from `data` that should be shown in a summary table.

    Drops labels, dividers, form-info fields, action-choice fields, and anything in
    `options["exclude"]` (in addition to the always-excluded `DEFAULT_EXCLUDE_FIELDS`).
    """
    exclude: set[str] = options.get("exclude", set()) | DEFAULT_EXCLUDE_FIELDS

    def should_include(field: str) -> bool:
        if "label" in field:
            return False
        if "divider" in field:
            return False
        if field.startswith("form_info"):
            return False
        if "action_choice_" in field:
            return False
        if field in exclude:
            return False
        return True

    return (field for field in data.keys() if should_include(field))


def _get_summary_labels(data: dict, options: BaseOptions) -> list[str]:
    """Returns filtered and formatted/translated labels for the given table."""
    formatters = DEFAULT_FORMATTERS | options.get("formatter", {})

    def get_label(field: str) -> Generator:
        formatter = formatters.get(field)

        if formatter:
            labels = [label for label, _ in formatter(data[field])]
            yield from labels
        else:
            yield get_summary_translation(field)

    field_labels = (get_label(field) for field in _filter_summary_fields(data, options))
    return list(chain.from_iterable(field_labels))


def _get_column_values(data: dict, options: BaseOptions) -> list[str]:
    """Returns filtered and formatted values for the given column."""
    formatters = DEFAULT_FORMATTERS | options.get("formatter", {})

    def get_value(field: str) -> Iterator[str]:
        field_value = data[field]
        if formatter := formatters.get(field):
            yield from (str(value) for _, value in formatter(field_value))
        else:
            match field_value:
                case None | []:
                    yield ""
                case {} if not field_value:
                    yield ""
                case _:
                    yield str(field_value)

    field_values = (get_value(field) for field in _filter_summary_fields(data, options))
    return list(chain.from_iterable(field_values))


def create_table(options: TableOptions, show_headers: bool = True) -> type[MigrationSummary]:
    """Creates a summary table that can be added as a field to the summary form.

    The table has columns with items of the same type.
    """

    def header(index: int) -> str:
        return options.get("header", str)(index)

    items = options["data"]
    first_item_data, _ = first(items)

    labels = _get_summary_labels(first_item_data, options)
    columns = [_get_column_values(item, options) for item, _ in items]
    headers = [header(index) for index in range(1, len(items) + 1)] if show_headers else []
    summary_data = SummaryData(labels=labels, columns=columns, headers=headers)  # type: ignore

    return migration_summary(data=summary_data)


def _table_number(*, table_data: dict, default: int) -> Any:
    """Pick the 1-based number to show for a table.

    Prefers `table_data["endpoint_nr"]` (0-based, converted to 1-based) over
    `table_data[TABLE_NUMBER_FIELD]`, and falls back to `default` when neither is set.
    """
    if (endpoint_nr := table_data.get("endpoint_nr")) is not None:
        return endpoint_nr + 1

    if (table_number := table_data.get(TABLE_NUMBER_FIELD)) is not None:
        return table_number

    return default


def _make_summary_table_header(options: TableOptions, index: int, default: str) -> str:
    """Create summary table header for given column using the header callable or the default."""
    if fn := options.get("header"):
        return fn(index)
    return default


def _generate_before_after_tables(options: TableOptions) -> FormFieldGenerator:
    """Creates one or more before and after summary tables that can be added as a field to the summary form.

    Instead of adding data items as columns to one and the same table (like create_table()) this creates a new
    table for each data item, with a before/after column.
    """

    after_items, _ = first(options["data"])

    labels = _get_summary_labels(after_items, options)
    default_headers = ["Before", "After"]
    headers = [
        _make_summary_table_header(options, index, default) for index, default in enumerate(default_headers, start=1)
    ]

    for num, (after, before) in enumerate(options["data"], 1):
        shown_index = _table_number(table_data=after, default=num)
        is_product_summary = options["name"] == PRODUCT_SUMMARY_TABLE_NAME
        table_name = options["name"] if is_product_summary else f"{options['name']} {shown_index}".strip()

        before_column: list[Any] = _get_column_values(before, options) if before else []
        after_column: list[Any] = _get_column_values(after, options)
        summary_data = SummaryData(labels=labels, columns=[before_column, after_column], headers=headers)
        yield table_name, (migration_summary(data=summary_data), None)


def _generate_single_column_tables(options: TableOptions) -> FormFieldGenerator:
    """Creates one or more single-column summary tables that can be added as a field to the summary form.

    Instead of adding data items as columns to one and the same table (like create_table()) this creates a new
    table for each data item, with a single column.
    """
    items = options["data"]

    first_item_data, _ = first(items)

    labels = _get_summary_labels(first_item_data, options)
    default_headers = [""]
    headers = [
        _make_summary_table_header(options, index, default) for index, default in enumerate(default_headers, start=1)
    ]

    for num, (kv, _) in enumerate(items, 1):
        shown_index = _table_number(table_data=kv, default=num)
        is_product_summary = options["name"] == PRODUCT_SUMMARY_TABLE_NAME
        table_name = options["name"] if is_product_summary else f"{options['name']} {shown_index}"

        single_column: list[Any] = _get_column_values(kv, options)
        summary_data = SummaryData(labels=labels, columns=[single_column], headers=headers)
        yield table_name, (migration_summary(data=summary_data), None)


def _validate_uniform_old_data(data: TableData) -> None:
    """Ensure a table's items are either all before/after pairs, or all plain (no old data).

    Mixing items with and without old data within one table is not supported. Use
    `make_table_data()` to build a consistent `data` sequence for a before/after table.
    """
    has_old_values = {bool(old) for _, old in data}
    if len(has_old_values) > 1:
        raise ValueError(
            "Inconsistent table data: either every item must have old data (before/after table) "
            "or none should (plain table) - mixing the two within one table is not supported. "
            "Use make_table_data() to build consistent before/after data."
        )


def _table_fields(table: TableOptions, index: int) -> FormFieldGenerator:
    """Creates a table summary field where the type is decided by the table data.

    Yields before and after table(s) if the TableOptions has property "data_before"
    Yields summary table if the TableOptions has property "data"
    Yields a message if the TableOptions has no "data" or "data_before"
    """
    yield f"divider_{index + 1}", (Divider, None)

    data_items = table.get("data", [])
    _validate_uniform_old_data(data_items)
    data = first(data_items, None)

    if data and data[1]:
        yield from _generate_before_after_tables(table)
    elif data and table.get("single_column"):
        yield from _generate_single_column_tables(table)
    elif data:
        is_not_first_table = bool(index)
        yield table["name"], (create_table(table, is_not_first_table), None)
    else:
        msg = table.get("empty_message", "no data")
        yield table["name"], (read_only_field(msg), msg)


def generate_summary_form(options: SummaryOptions) -> Generator:
    """Generate summary form for a workflow.

    Expects atleast a "product" to create the product summary table.
    May contain extra summary tables for additional forms such as created endpoints.
    """

    class SummaryFormPage(SubmitFormPage):
        model_config = ConfigDict(title=f"{options['product_name']} Summary")

    product_fields = dict(_table_fields(options["product"], 0))
    after_product = options.get("after_product", {})  # e.g. show callout
    remaining_tables = options.get("tables", [])
    remaining_fields = dict(
        chain.from_iterable(_table_fields(table, index) for index, table in enumerate(remaining_tables, start=1))
    )
    all_fields = product_fields | after_product | remaining_fields
    yield create_model("SummaryFormPage", __base__=SummaryFormPage, **all_fields)  # type: ignore


def make_table_data(
    new_data: Sequence[dict], old_data: Iterable[dict | None] | None = None
) -> Sequence[tuple[dict, dict | None]]:
    """Pair up `new_data` items with the corresponding `old_data` items for use as `TableOptions["data"]`.

    Use this to build "data" for a before/after table, e.g. when modifying a list of endpoints. If
    `old_data` is omitted or empty, every item is paired with `None` (a plain, non-before/after table).

    Note: if `old_data` is shorter than `new_data`, `zip` truncates and the extra `new_data`
    items are silently dropped — make sure both sequences have matching lengths when both are given.

    >>> make_table_data([{"a": 1}, {"a": 2}])
    [({'a': 1}, None), ({'a': 2}, None)]
    >>> make_table_data([{"a": 1}], [{"a": 0}])
    [({'a': 1}, {'a': 0})]
    >>> make_table_data([{"a": 1}, {"a": 2}], [{"a": 0}])
    [({'a': 1}, {'a': 0})]
    >>> make_table_data([{"a": 1}, {"a": 2}], [])
    [({'a': 1}, None), ({'a': 2}, None)]
    """
    return list(zip(new_data, old_data if old_data else itertools.repeat(None)))


def base_summary(
    product_name: str,
    new_data: dict,
    old_data: dict | None = None,
    tables: Sequence[TableOptions] = (),
) -> Generator:
    """Build a summary form for a single product table, optionally with extra tables.

    This is a shortcut for `generate_summary_form()`: it wraps `new_data`/`old_data` into a single
    "product_summary" table (before/after if `old_data` is given) and appends any extra `tables`.
    Use `generate_summary_form()` directly when you need more control or no product summary table.
    """
    summary_options = SummaryOptions(
        product_name=product_name,
        product=TableOptions(
            name=PRODUCT_SUMMARY_TABLE_NAME,
            data=[(new_data, old_data)],
        ),
        tables=tables,
    )

    return generate_summary_form(summary_options)


def subscription_summary_fields(subscription_id: UUID) -> RowGenerator:
    """Formatter that yields subscription id, description, and block title rows for a linked subscription.

    Use as a `Formatter` (in `DEFAULT_FORMATTERS` or a table's `options["formatter"]`) for a field that
    holds another subscription's id, e.g. one subscription referencing another it depends on. Falls
    back to "-" for the title when the subscription's first product block has no `title` attribute.
    """
    subscription = SubscriptionModel.from_subscription(subscription_id)
    block_name = first(subscription._product_block_fields_.keys())
    block = getattr(subscription, block_name, None)
    block_title = getattr(block, "title", "-") if block else "-"

    yield get_field_translation("subscription_id"), str(subscription.subscription_id)
    yield get_field_translation("description"), subscription.description
    yield get_field_translation("title"), block_title


def customer_name_summary_field(
    get_customer_name_fn: Callable[[UUID | UUIDstr], str],
) -> Callable[[UUIDstr], RowGenerator]:
    """Build a `Formatter` for a customer id field that shows the resolved customer name instead of the raw id.

    Pass a lookup function that resolves a customer id to a name; register the returned formatter under
    the relevant field key, e.g. `DEFAULT_FORMATTERS["customer_id"] = customer_name_summary_field(...)`.

    >>> list(customer_name_summary_field(lambda customer_id: "ACME")("cust-1"))
    [('customer_id', 'ACME')]
    >>> list(customer_name_summary_field(lambda customer_id: None)("cust-2"))
    [('customer_id', 'Customer name not found for cust-2')]
    """

    def _customer_name_summary_field(customer_id: UUIDstr) -> RowGenerator:
        """Formatter for showing customer name with the customer_id."""
        customer_name = get_customer_name_fn(customer_id)
        yield get_field_translation("customer_id"), customer_name or f"Customer name not found for {customer_id}"

    return _customer_name_summary_field


def select_list_summary(field_name: str) -> Callable[[list], RowGenerator]:
    """Build a `Formatter` for a multi-select list field that joins the selected values into one row.

    Register the returned formatter under the relevant field key, e.g.
    `DEFAULT_FORMATTERS["tags"] = select_list_summary("tags")`.

    >>> list(select_list_summary("prefixes")(["1.1.1.1/32", "2.2.2.2/32"]))
    [('prefixes', '1.1.1.1/32, 2.2.2.2/32')]
    >>> list(select_list_summary("prefixes")([]))
    [('prefixes', '')]
    """

    def _select_list_summary(list: list[str]) -> RowGenerator:
        """Formatter for IPV X prefix list."""
        yield get_summary_translation(field_name), ", ".join(list)

    return _select_list_summary


DEFAULT_FORMATTERS: dict[str, Formatter] = {}
