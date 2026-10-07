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

"""The agent-facing page spec: what ``form_fields`` says about each kind of field a form can declare."""

from typing import Any, Literal
from uuid import UUID

import pytest
from pydantic import BaseModel, ConfigDict, Field

from orchestrator.core.forms import FormPage
from orchestrator.core.forms.spec import form_fields
from orchestrator.core.forms.validators import CustomerId, DisplaySubscription
from pydantic_forms.validators import (
    Accept,
    Choice,
    Label,
    choice_list,
    migration_summary,
    read_only_field,
)

SUBSCRIPTION_ID = UUID("11111111-2222-3333-4444-555555555555")
SUMMARY = {"labels": ["speed"], "columns": [["10G"]]}


class Color(Choice):
    red = ("red", "Red")
    blue = ("blue", "Blue")


NoColor = Choice.__call__("NoColor", {})  # a choice the form has no option for today


class Person(BaseModel):
    name: str
    phone: str | None = None


class Page(FormPage):
    model_config = ConfigDict(title="Every kind of field")

    heading: Label
    recap: migration_summary(SUMMARY)
    shown: DisplaySubscription = SUBSCRIPTION_ID
    fixed: read_only_field("fixed")
    consent: Accept
    color: Color
    colors: choice_list(Color, min_items=1, max_items=2, unique_items=True)
    one_color: choice_list(Color, max_items=1)
    no_color: NoColor
    mode: Literal["a", "b"] = "a"
    ratio: float | None = None
    flag: bool = False
    customer: CustomerId
    people: list[Person] = Field(default_factory=list)


FIELDS = {field.name: field.model_dump() for field in form_fields(Page)}
COLORS = [{"value": "red", "label": "Red"}, {"value": "blue", "label": "Blue"}]


def _subset(actual: Any, expected: Any) -> bool:
    """Whether ``expected`` is in ``actual``: every key of a dict, every item of a list, equal otherwise."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(_subset(actual.get(key), value) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(map(_subset, actual, expected))
    return bool(actual == expected)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        pytest.param(
            "heading", {"kind": "string", "format": "label", "display_only": True, "required": False}, id="label"
        ),
        pytest.param(
            "recap", {"kind": "any", "format": "summary", "display_only": True, "data": SUMMARY}, id="summary"
        ),
        pytest.param(
            "shown",
            {"format": "subscription", "display_only": True, "default": str(SUBSCRIPTION_ID)},
            id="subscription",
        ),
        pytest.param(
            "fixed", {"kind": "string", "read_only": True, "display_only": False, "default": "fixed"}, id="read-only"
        ),
        pytest.param(
            "consent",
            {"format": "accept", "required": True, "options": [{"value": "ACCEPTED", "label": "ACCEPTED"}]},
            id="accept",
        ),
        pytest.param("color", {"kind": "string", "required": True, "default": None, "options": COLORS}, id="choice"),
        pytest.param(
            "colors",
            {"kind": "list", "min_items": 1, "max_items": 2, "unique_items": True, "item": {"options": COLORS}},
            id="choice-list",
        ),
        pytest.param(
            "one_color", {"kind": "list", "min_items": 0, "max_items": 1, "unique_items": False}, id="list-of-one"
        ),
        pytest.param("no_color", {"options": []}, id="choice-without-options"),
        pytest.param(
            "mode",
            {
                "kind": "string",
                "required": False,
                "default": "a",
                "options": [{"value": "a", "label": "a"}, {"value": "b", "label": "b"}],
            },
            id="literal",
        ),
        pytest.param(
            "ratio", {"kind": "number", "nullable": True, "required": False, "default": None}, id="optional-number"
        ),
        pytest.param("flag", {"kind": "boolean", "default": False}, id="boolean"),
        pytest.param(
            "customer", {"kind": "string", "format": "customerId", "required": True, "options": None}, id="customer-id"
        ),
        pytest.param(
            "people",
            {
                "kind": "list",
                "default": [],
                "item": {
                    "kind": "object",
                    "required": False,
                    "fields": [
                        {"name": "name", "kind": "string", "required": True},
                        {"name": "phone", "nullable": True},
                    ],
                },
            },
            id="nested-models",
        ),
    ],
)
def test_field_spec(name, expected):
    assert _subset(FIELDS[name], expected), FIELDS[name]


def test_fields_keep_the_forms_order_and_are_titled():
    assert list(FIELDS) == list(Page.model_fields)
    assert FIELDS["no_color"]["title"] == "No Color"  # pydantic's own humanisation of a name without a title
