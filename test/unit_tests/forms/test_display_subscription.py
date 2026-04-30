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

from uuid import uuid4

from orchestrator.core.forms.validators import DisplaySubscription, Label, migration_summary
from pydantic_forms.core import FormPage


def test_display_subscription():
    some_sub_id = uuid4()

    class Form(FormPage):
        display_sub: DisplaySubscription = some_sub_id

    expected = {"display_sub": some_sub_id}

    assert Form().model_dump() == expected


def test_display_subscription_update_not_allowed():
    some_sub_id = uuid4()

    class Form(FormPage):
        display_sub: DisplaySubscription = some_sub_id

    expected = {"display_sub": some_sub_id}

    assert Form(display_sub=uuid4()).model_dump() == expected


def test_display_only_schema():
    some_sub_id = uuid4()
    Summary = migration_summary({"headers": ["one"]})

    class Form(FormPage):
        display_sub: DisplaySubscription = some_sub_id
        label: Label
        summary: Summary

    expected = {
        "$defs": {
            "MigrationSummaryValue": {
                "properties": {},
                "title": "MigrationSummaryValue",
                "type": "object",
            },
        },
        "additionalProperties": False,
        "properties": {
            "display_sub": {
                "default": str(some_sub_id),
                "format": "subscription",
                "title": "Display Sub",
                "type": "string",
            },
            "label": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "format": "label",
                "default": None,
                "title": "Label",
                "type": "string",
            },
            "summary": {
                "$ref": "#/$defs/MigrationSummaryValue",
                "format": "summary",
                "default": None,
                "type": "string",
                "uniforms": {"data": {"headers": ["one"]}},
                "extraProperties": {"data": {"headers": ["one"]}},
            },
        },
        "title": "unknown",
        "type": "object",
    }

    assert Form.model_json_schema() == expected
