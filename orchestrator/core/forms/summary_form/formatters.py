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

from collections.abc import Callable, Generator
from typing import Any
from uuid import UUID

from more_itertools import first

from orchestrator.core.domain import SubscriptionModel
from pydantic_forms.types import UUIDstr

RowGenerator = Generator[tuple[str, str], None, None]

Formatter = Callable[[Any], RowGenerator]

DEFAULT_FORMATTERS: dict[str, Formatter] = {}


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

    yield "subscription_id", str(subscription.subscription_id)
    yield "description", subscription.description
    yield "title", block_title


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
        yield "customer_id", customer_name or f"Customer name not found for {customer_id}"

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

    def _select_list_summary(_list: list[str]) -> RowGenerator:
        """Formatter for IPV X prefix list."""
        yield field_name, ", ".join(_list)

    return _select_list_summary
