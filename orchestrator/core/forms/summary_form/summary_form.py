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

from collections.abc import Callable, Generator, Iterable, Iterator, Sequence
from itertools import chain, repeat
from typing import Any, Required, TypedDict

from more_itertools import first
from pydantic import BaseModel, ConfigDict, create_model
from pydantic.fields import FieldInfo

from orchestrator.core.forms import FormPage, SubmitFormPage
from orchestrator.core.forms.summary_form.formatters import DEFAULT_FORMATTERS, Formatter
from orchestrator.core.forms.validators import Divider, Label, MigrationSummary, migration_summary
from pydantic_forms.types import SummaryData
from pydantic_forms.validators import callout, read_only_field

FormFieldGenerator = Generator[tuple[str, tuple], None, None]
FormPageGenerator = Generator[type[FormPage], None, None]
TableData = Sequence[tuple[dict, dict | None]]


TABLE_NUMBER_FIELD = "__table_number"

PRODUCT_SUMMARY_TABLE_NAME = "product_summary"


class BaseOptions(TypedDict, total=False):
    formatter: dict[str, Formatter]
    """Per-field `Formatter` overrides of `DEFAULT_FORMATTERS`."""


class TableOptions(BaseOptions, total=False):
    name: Required[str]
    """Table title, and field name prefix on the generated form."""

    header: Callable[[Any], str]
    """Computes a column header from its 1-based index."""

    data: Required[TableData]
    """Sequence[(new: dict, old: dict | None)] - the rows to render."""

    empty_message: str
    """Message shown when `data` is empty."""

    single_column: bool
    """Set True to render one table per item, instead of one combined table."""


class SummaryOptions(TypedDict, total=False):
    product_name: Required[str]
    """Title of the generated summary `FormPage`."""

    product: Required[TableOptions]

    after_product: dict[str, tuple]
    """Extra fields merged in after the product table, e.g. to show a callout."""

    tables: Sequence[TableOptions]
    """Any number of extra tables, e.g. one per endpoint a workflow is creating."""


def _filter_summary_fields(data: dict) -> Generator[str, None, None]:
    """Yield the field names from `data` that should be shown in a summary table.

    Drops `TABLE_NUMBER_FIELD` (a summary-form internal). Callers are responsible for excluding
    anything else (e.g. UI-only fields) before building table data - see `extract_user_input()`.
    """
    return (field for field in data.keys() if field != TABLE_NUMBER_FIELD)


def _field_format(json_schema_extra: Any) -> str | None:
    """Return the "format" key a field's `json_schema_extra` renders as, dict- or callable-based."""
    if isinstance(json_schema_extra, dict):
        return json_schema_extra.get("format")
    if callable(json_schema_extra):
        schema: dict[str, Any] = {}
        json_schema_extra(schema)
        return schema.get("format")
    return None


def _format_marker(annotated_type: Any) -> str | None:
    """Return the format marker of an Annotated field type, if any."""
    for meta in getattr(annotated_type, "__metadata__", ()):
        if fmt := _field_format(getattr(meta, "json_schema_extra", None)):
            return fmt
    return None


DEFAULT_EXCLUDED_TYPES = (
    Divider,
    Label,
    migration_summary(data=SummaryData(labels=[], columns=[])),
    callout(),
)


def extract_user_input(form: BaseModel, *, exclude_types: Iterable[Any] = ()) -> dict:
    """`model_dump()` a form, dropping its Label/Divider/summary-table/callout fields.

    Use this instead of `form.model_dump()` wherever a form is dumped: these field types are
    UI-only display elements - their model value is always `None` (the displayed content lives in
    the type's schema, not the field's value) - so they never carry real data, in a summary table
    or anywhere else. Pass `exclude_types` for other display-only field types defined the same way
    (an `Annotated[..., Field(json_schema_extra=...)]` alias).
    """
    excluded_formats = {fmt for t in (*DEFAULT_EXCLUDED_TYPES, *exclude_types) if (fmt := _format_marker(t))}

    def is_excluded(field: FieldInfo) -> bool:
        return _field_format(field.json_schema_extra) in excluded_formats

    exclude = {name for name, field in type(form).model_fields.items() if is_excluded(field)}
    return form.model_dump(exclude=exclude)


def exclude_summary_fields(data: dict, fields: Iterable[str]) -> dict:
    """Drop `fields` from `data` before it's used to build a summary table.

    Use this for fields that must stay in the workflow's persisted state (so keep them out of
    `extract_user_input`) but shouldn't be shown to the user in a summary table - e.g. a workflow's
    own action-choice fields.
    """
    fields = set(fields)
    return {key: value for key, value in data.items() if key not in fields}


def _get_summary_labels(data: dict, options: BaseOptions) -> list[str]:
    """Returns filtered and formatted/translated labels for the given table."""
    formatters = DEFAULT_FORMATTERS | options.get("formatter", {})

    def get_label(field: str) -> Generator:
        formatter = formatters.get(field)

        if formatter:
            labels = [label for label, _ in formatter(data[field])]
            yield from labels
        else:
            yield field

    field_labels = (get_label(field) for field in _filter_summary_fields(data))
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

    field_values = (get_value(field) for field in _filter_summary_fields(data))
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


def _table_number(*, table_data: dict, default: int) -> str:
    """Pick the `_<n>` suffix to append to a per-item table's name.

    Uses `table_data[TABLE_NUMBER_FIELD]` if set, otherwise falls back to `_<default>`.
    """
    return f"_{table_data.get(TABLE_NUMBER_FIELD, default)}"


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
    default_headers = ["before", "after"]
    headers = [
        _make_summary_table_header(options, index, default) for index, default in enumerate(default_headers, start=1)
    ]

    for num, (after, before) in enumerate(options["data"], 1):
        shown_index = _table_number(table_data=after, default=num)
        is_product_summary = options["name"] == PRODUCT_SUMMARY_TABLE_NAME
        table_name = options["name"] if is_product_summary else f"{options['name']}{shown_index}"

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
        table_name = options["name"] if is_product_summary else f"{options['name']}{shown_index}"

        single_column: list[Any] = _get_column_values(kv, options)
        summary_data = SummaryData(labels=labels, columns=[single_column], headers=headers)
        yield table_name, (migration_summary(data=summary_data), None)


def _validate_uniform_old_data(table_name: str, data: TableData) -> None:
    """Ensure a table's items are either all before/after pairs, or all plain (no old data).

    Mixing items with and without old data within one table is not supported. Use
    `make_table_data()` to build a consistent `data` sequence for a before/after table.
    """
    has_old_values = {bool(old) for _, old in data}
    if len(has_old_values) > 1:
        raise ValueError(
            f"Inconsistent table data for '{table_name}': either every item must have old data "
            "(before/after table) or none should (plain table) - mixing the two within one table "
            "is not supported. Use make_table_data() to build consistent before/after data."
        )


def _table_fields(table: TableOptions, index: int) -> FormFieldGenerator:
    """Creates a table summary field where the type is decided by the table data.

    Yields before and after table(s) if the TableOptions has property "data_before"
    Yields summary table if the TableOptions has property "data"
    Yields a message if the TableOptions has no "data" or "data_before"
    """
    yield f"divider_{index + 1}", (Divider, None)

    data_items = table.get("data", [])
    _validate_uniform_old_data(table["name"], data_items)
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
    return list(zip(new_data, old_data if old_data else repeat(None)))


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
