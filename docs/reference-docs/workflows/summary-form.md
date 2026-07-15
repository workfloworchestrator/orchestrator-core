# Summary Forms

Before a create or modify workflow submits its input, it is common to show the operator a
read-only recap of everything that is about to change: the values just entered, and — for modify
workflows — what they looked like before. `orchestrator.core.forms.summary_form` provides a
small toolkit for building this recap page (a "summary form") without having to hand-write a
`FormPage` for every workflow.

The recap is rendered by the frontend as one or more read-only tables, using the same
`MigrationSummary` field type that regular `FormPage`s use for any other input.

## Quick start

For the common case — a single product table, optionally compared against its previous values —
use `base_summary`. It is a generator, so it must be delegated to with `yield from` at the end of
an `initial_input_form_generator`:

```python
from orchestrator.core.forms.summary_form import base_summary


def initial_input_form_generator(product: UUID, product_name: str) -> FormGenerator:
    class SelectOptionsForm(FormPage):
        model_config = ConfigDict(title=product_name)

        speed: int
        vlan: int

    user_input = yield SelectOptionsForm

    yield from base_summary(product_name, user_input.model_dump())

    return user_input.model_dump()
```

This yields a `FormPage` titled `f"{product_name} Summary"` containing one table with a row per
field of `user_input`. For a modify workflow, pass the subscription's current values as `old_data`
to render a **before / after** table instead:

```python
yield from base_summary(product_name, new_data=user_input.model_dump(), old_data=previous_values)
```

## Multiple tables: `generate_summary_form` and `SummaryOptions`

`base_summary` is a thin wrapper around `generate_summary_form`, which accepts a `SummaryOptions`
dict describing the product table plus any number of extra tables (for example, one table per
endpoint that a workflow is creating):

```python
from orchestrator.core.forms.summary_form import (
    SummaryOptions,
    TableOptions,
    generate_summary_form,
    make_table_data,
)

summary_options = SummaryOptions(
    product_name=product_name,
    product=TableOptions(
        name="product_summary",
        data=[(user_input.model_dump(), None)],
    ),
    tables=[
        TableOptions(
            name="endpoint",
            data=make_table_data(new_endpoints, old_endpoints),
            empty_message="No endpoints",
        ),
    ],
)
yield from generate_summary_form(summary_options)
```

`make_table_data(new_data, old_data=None)` zips a list of new items with the corresponding list of
old items (or `None` for every item, if there is nothing to compare against) into the
`(new, old)` tuples that `TableOptions["data"]` expects.

### How a table is rendered

For each `TableOptions`, `generate_summary_form` picks the table layout based on the data it is
given:

| Situation | Layout |
|---|---|
| `data` is empty | A single read-only row showing `empty_message` (default `"no data"`) |
| Every item's `old` value is falsy | One table with one **column per item** |
| An item's `old` value is truthy | One **Before / After** table per item |
| `single_column=True` | One single-column table per item, instead of one combined table |

Use `single_column=True` when the items don't share a natural "before/after" or "side by side"
relationship and read better as their own standalone tables (for example, a list of dissimilar
endpoints).

### `TableOptions` reference

| Key | Purpose |
|---|---|
| `name` | Table title, and field name prefix on the generated form |
| `data` | `Sequence[(new: dict, old: dict \| None)]` — the rows to render |
| `exclude` | Field names to omit from every row |
| `formatter` | Per-field `Formatter` overrides, see below |
| `header` | `Callable[[int], str]` to compute a column header from its 1-based index |
| `empty_message` | Message shown when `data` is empty |
| `single_column` | Render one table per item instead of one combined table |

`SummaryOptions` additionally accepts `after_product` (extra fields merged in after the product
table, e.g. to show a callout) and `tables` (the list of extra `TableOptions` described above).

## Custom field formatters

By default, a field is shown as its translated field name and `str(value)`. Some fields need
richer rendering — for example a subscription ID that should show the linked subscription's
description, or a composite value that should expand into several rows. A `Formatter` does this:

```python
from collections.abc import Generator

RowGenerator = Generator[tuple[str, str], None, None]


def notification_summary(notification: dict) -> RowGenerator:
    """Expand a single `notification` field into three summary rows."""
    enabled = notification["enabled"]
    yield "Notifications enabled", str(enabled)
    yield "Channel", notification["channel"] if enabled else "N/A"
```

A `Formatter` is any `Callable[[Any], RowGenerator]`: given the field's value, it yields
`(label, value)` pairs — usually one, but as many as needed.

There are two ways to plug a formatter in:

* **Per table**, via `TableOptions(formatter={"notification": notification_summary, ...})` — only
  applies to that table.
* **Globally**, by adding it to `DEFAULT_FORMATTERS` — applies to every summary table in the
  process, keyed by field name:

  ```python
  from orchestrator.core.forms.summary_form import DEFAULT_FORMATTERS

  DEFAULT_FORMATTERS.update({"notification": notification_summary})
  ```

`DEFAULT_FORMATTERS` is a plain, shared, mutable dict, so downstream applications typically extend
it once at import time — for example in a module that every workflow package is guaranteed to
import before it builds its first summary form — rather than passing `formatter=` everywhere a
field shows up. A handful of general-purpose formatters ship out of the box:

* `customer_name_summary_field(get_customer_name_fn)` — returns a formatter that resolves a
  customer id to its display name via the callable you provide.
* `select_list_summary(field_name)` — returns a formatter that joins a list field into a single,
  comma-separated row.
* `subscription_summary_fields(subscription_id)` — not a `Formatter` itself, but a helper that
  yields the standard `(subscription_id, description, title)` rows for a related subscription;
  handy to reuse from your own formatters (as `notification_summary` above could, if its field
  also embedded a related subscription).

## API summary

All of the above is importable from `orchestrator.core.forms.summary_form`:

| Name | Purpose |
|---|---|
| `base_summary` | Single product table, with optional before/after comparison |
| `generate_summary_form` | Full control via `SummaryOptions` / `TableOptions` |
| `create_table` | Build a single table's `MigrationSummary` field directly |
| `make_table_data` | Zip new/old item lists into `TableOptions["data"]` |
| `SummaryOptions`, `TableOptions`, `BaseOptions` | Option `TypedDict`s |
| `DEFAULT_FORMATTERS` | Global, mutable field-name → `Formatter` registry |
| `Formatter`, `RowGenerator` | Type aliases for writing your own formatters |
| `customer_name_summary_field`, `select_list_summary`, `subscription_summary_fields` | Built-in formatter helpers |
| `get_field_translation`, `get_summary_translation` | Look up the translated label for a field name |
