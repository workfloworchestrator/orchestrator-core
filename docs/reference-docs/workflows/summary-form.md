# Summary Forms

!!! info "New in `orchestrator-core` 5.2.0"
    `orchestrator.core.forms.summary_form` is a new module — there is no equivalent toolkit in
    earlier versions. Before 5.2.0, workflows built their own recap page by hand-writing a
    `FormPage` with `MigrationSummary` fields.

Before a create or modify workflow submits its input, it is common to show the user a
read-only recap of everything that is about to change: the values just entered, and — for modify
workflows — what they looked like before. `orchestrator.core.forms.summary_form` provides a
small toolkit for building this recap page (a "summary form") without having to hand-write a
`FormPage` for every workflow.

The recap is rendered by the frontend as one or more read-only tables, using the same
`MigrationSummary` field type.

## Quick start

For the common case — a single product table, optionally compared against its previous values —
use `base_summary`. It is a generator, so it must be delegated to with `yield from` at the end of
an `initial_input_form_generator`:

=== "`orchestrator-core` ≥ 5.2.0"

    ```python
    from orchestrator.core.forms.summary_form import base_summary, extract_user_input


    def initial_input_form_generator(product: UUID, product_name: str) -> FormGenerator:
        class InputForm(FormPage):
            model_config = ConfigDict(title=product_name)

            speed: int
            vlan: int
            exclude_from_summary: str

        user_input = yield InputForm
        user_input_data = extract_user_input(user_input)
        summary_data = exclude_summary_fields(user_input_data, {"exclude_from_summary"})

        yield from base_summary(product_name, user_input_data)

        return user_input_data
    ```

This yields a `FormPage` titled `f"{product_name} Summary"` containing one table with a row per
field of `user_input`.

!!! note "Non-data fields in a form's dump"
    A form's dump generally includes non-data fields too, e.g. `Divider` and `Label` fields used
    to visually group the form. Use `extract_user_input(form)` instead of `form.model_dump()`
    everywhere a form is dumped — it drops any `Divider`/`Label` field automatically (matched by
    field *type*, not by name, so a real data field happening to be called e.g. `label_color` is
    never affected). Pass `exclude_types` for other display-only field types defined the same way.

    Fields with a real value that need more context (e.g. showing `customer_id` as a customer name
    instead of a raw UUID) should use a formatter instead, see below.

!!! note "Fields that belong in state but not in the summary"
    Some fields must stay in the data returned from `extract_user_input` (the workflow still needs
    them, e.g. a per-item action-choice field driving what happens next) but shouldn't be shown to
    the user in the summary table. Apply `exclude_summary_fields` as a second step, only on the
    data passed into `base_summary`/`generate_summary_form`/`TableOptions`, not on the data
    returned from the step:

    === "`orchestrator-core` ≥ 5.2.0"

        ```python
        form_data = exclude_summary_fields(user_input_data, {"peer_action_choice_1"})
        yield from base_summary(product_name, form_data)
        ```

For a modify workflow, pass the subscription's current values as `old_data`
to render a **before / after** table instead:

=== "`orchestrator-core` ≥ 5.2.0"

    ```python
    yield from base_summary(product_name, new_data=user_input_data, old_data=previous_values)
    ```

## Multiple tables: `generate_summary_form` and `SummaryOptions`

`base_summary` is a thin wrapper around `generate_summary_form`, which accepts a `SummaryOptions`
dict describing the product table plus any number of extra tables (for example, one table per
item a workflow is creating):

=== "`orchestrator-core` ≥ 5.2.0"

    ```python
    from orchestrator.core.forms.summary_form import (
        SummaryOptions,
        TableOptions,
        extract_user_input,
        generate_summary_form,
        make_table_data,
    )

    summary_options = SummaryOptions(
        product_name=product_name,
        product=TableOptions(
            name="product_summary",
            data=[(extract_user_input(user_input), None)],
        ),
        tables=[
            TableOptions(
                name="item",
                data=make_table_data(new_items, old_items),
                empty_message="No items",
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
| No item has an `old` value | One table with one **column per item** |
| An item has an `old` value | One **Before / After** table per item |
| `single_column=True` | One single-column table per item, instead of one combined table |

Use `single_column=True` when items don't share a natural "before/after" or "side by side"
relationship (for example, a list of dissimilar ports).

### Before/after table example

Passing a truthy `old` value alongside a `new` item renders a **Before/After** table for that item
(one table per item, not one combined table). A full modify workflow comparing a list of ports
before and after the user edits them:

=== "`orchestrator-core` ≥ 5.2.0"

    ```python
    from pydantic import ConfigDict
    from pydantic_forms.types import FormGenerator

    from orchestrator.core.forms import FormPage
    from orchestrator.core.forms.summary_form import (
        SummaryOptions,
        TableOptions,
        extract_user_input,
        generate_summary_form,
        make_table_data,
    )


    def modify_ports_generator(ports: list[Port]) -> FormGenerator:
        old_ports = [{"description": port.description, "vlan": port.vlan} for port in ports]

        new_ports = []
        for port in ports:

            class EditPortForm(FormPage):
                model_config = ConfigDict(title=f"Edit port {port.vlan}")

                description: str = port.description
                vlan: int = port.vlan

            port_input = yield EditPortForm
            new_ports.append(extract_user_input(port_input))

        summary_options = SummaryOptions(
            product_name="Ports",
            product=TableOptions(
                name="ports_summary",
                data=make_table_data(new_ports, old_ports),
            ),
        )
        yield from generate_summary_form(summary_options)
    ```

If the user changes port 1's `vlan` from `100` to `150` and leaves port 2
untouched, the result is two separate before/after tables:

```text
  ports_summary_1                        ports_summary_2
| field       | before | after    |    | field       | before  | after   |
|-------------|--------|----------|    |-------------|---------|---------|
| description | Port 1 | Port 1   |    | description | port 2  | port 2  |
| vlan        | 100    | 150      |    | vlan        | 200     | 200     |
```

`generate_summary_form` doesn't diff field-by-field or hide unchanged rows - it renders whatever
`old`/`new` data you give it, so an untouched port's table still shows identical before/after
columns. If you only want to show items that actually changed, filter `ports` (or `new_ports`/
`old_ports`) down to the changed ones before calling `make_table_data`.

Per-item tables are numbered by their position in `data` by default (`item_1`, `item_2`, ...). If
items carry their own identity that predates the summary (for example, numbered slots where one
can be removed), set `TABLE_NUMBER_FIELD` (`"__table_number"`) on an item's `new` dict to keep its
original number instead of renumbering by position:

=== "`orchestrator-core` ≥ 5.2.0"
    ```python
    tables = [
        TableOptions(
            name="item",
            data=make_table_data(
                [{**item, TABLE_NUMBER_FIELD: original_index} for original_index, item in surviving_items]
            ),
        ),
    ]
    ```


## Custom field formatters

By default, a field is shown as its field name and `str(value)`; the frontend translates the field
name the same way it translates any other form field (falling back to the raw name if no
translation exists).

For fields that need custom rendering, for example a subscription ID that
shows the linked subscription's description or a composite value that expands into
several rows, a `Formatter` can be used:

=== "`orchestrator-core` ≥ 5.2.0"

    ```python
    from collections.abc import Generator

    RowGenerator = Generator[tuple[str, str], None, None]


    def notification_summary(notification: dict) -> RowGenerator:
        """Expand a single `notification` field into two summary rows."""
        enabled = notification["enabled"]
        yield "Notifications enabled", str(enabled)
        yield "Channel", notification["channel"] if enabled else "N/A"
    ```

A `Formatter` is any `Callable[[Any], RowGenerator]` that given the field's value yields one or more `(label, value)` pairs.

There are two ways to use a formatter:

* **Per table**, via `TableOptions(formatter={"notification": notification_summary, ...})` — only
  applies to that table.
* **Globally**, by adding it to `DEFAULT_FORMATTERS` — applies to every summary table in your workflows, keyed by field name:

=== "`orchestrator-core` ≥ 5.2.0"
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
  also embedded a related subscription). For example, an L2VPN endpoint holds a `sap` field whose
  `port` is a reference to the port subscription it's attached to (see
  [`example-orchestrator`](https://github.com/workfloworchestrator/example-orchestrator) for more
  on the L2VPN product and its SAPs) — build a formatter for it that re-uses
  `subscription_summary_fields` for the port's own rows, then adds the SAP's VLAN range:

=== "`orchestrator-core` ≥ 5.2.0"
    ```python
    from orchestrator.core.forms.summary_form import DEFAULT_FORMATTERS, RowGenerator, subscription_summary_fields


    def sap_summary(sap: dict) -> RowGenerator:
        owner_subscription_id = sap.get("port", {}).get("owner_subscription_id")
        if owner_subscription_id:
            yield from subscription_summary_fields(owner_subscription_id)
            yield "vlan", sap["vlanrange"]


    DEFAULT_FORMATTERS.update({"sap": sap_summary})
    ```

  With `sap_summary` registered, a table of endpoints where each item has a `sap` field renders the
  port's `subscription_id`, `description` and `title` plus `vlan` for every endpoint, instead of a
  single row with the raw `sap` dict:

=== "`orchestrator-core` ≥ 5.2.0"
    ```python
    tables = [
        TableOptions(
            name="endpoint",
            data=make_table_data([{"sap": endpoint.sap} for endpoint in new_endpoints]),
        ),
    ]
    ```

## API summary

All of the above is importable from `orchestrator.core.forms.summary_form`:

::: orchestrator.core.forms.summary_form
    options:
      docstring_style: google
      separate_signature: true
      show_root_heading: false
      show_root_toc_entry: false
      show_symbol_type_heading: true
      show_symbol_type_toc: true
      members:
        - base_summary
        - generate_summary_form
        - create_table
        - make_table_data
        - extract_user_input
        - exclude_summary_fields
        - SummaryOptions
        - TableOptions
        - BaseOptions
        - customer_name_summary_field
        - select_list_summary
        - subscription_summary_fields
