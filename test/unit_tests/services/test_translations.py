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

import json
import pathlib
import tempfile

import pytest

from orchestrator.core.services import translations
from orchestrator.core.services.translations import generate_translations
from orchestrator.core.settings import app_settings


def test_generate_translations_empty():
    assert generate_translations("") == {}


def test_generate_translations():
    assert generate_translations("en-GB")


def test_generate_translations_custom_file():
    old_value = app_settings.TRANSLATIONS_DIR
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(f"{temp_dir}/nl-NL.json", "w") as temp_file:
                temp_file.write("[]")

            app_settings.TRANSLATIONS_DIR = pathlib.Path(temp_dir)

            assert generate_translations("nl-NL") == {}

            with open(f"{temp_dir}/nl-NL.json", "w") as temp_file:
                temp_file.write('{"foo": {"key1": "val1", "key2":"val2"}}')

            assert generate_translations("nl-NL") == {"foo": {"key1": "val1", "key2": "val2"}}

            app_settings.TRANSLATIONS_DIR = old_value

    finally:
        app_settings.TRANSLATIONS_DIR = old_value


def test_generate_translations_extend_default():
    old_value = app_settings.TRANSLATIONS_DIR
    custom_translations = {
        "forms": {
            "fields": {"note": "Overwritten note entry", "new_field": "New field entry"},
            "new_form_key": "New form value",
        },
        "new_top_level_key": {"new_key": "new_value"},
        "workflow": {"new_wf_translation": "New workflow entry"},
    }
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(f"{temp_dir}/en-GB.json", "w") as temp_file:
                temp_file.write(json.dumps(custom_translations))

            app_settings.TRANSLATIONS_DIR = pathlib.Path(temp_dir)
            result = generate_translations("en-GB")

            assert set(result.keys()) == {"forms", "workflow", "new_top_level_key"}
            assert result.get("forms", {}).get("new_form_key") == "New form value"
            assert "modify_note" in result.get("workflow", {})
    finally:
        app_settings.TRANSLATIONS_DIR = old_value


@pytest.mark.parametrize(
    "table,expected",
    [
        pytest.param(
            {"forms": {"fields": {"note": "Notes", "note_info": "Help"}}},
            {"note": "Notes", "note_info": "Help"},
            id="labels",
        ),
        pytest.param(
            {"forms": {"fields": {"note": "Notes", "nested": {"x": "y"}}}}, {"note": "Notes"}, id="only-strings"
        ),
        pytest.param({"workflow": {}}, {}, id="no-forms-table"),
    ],
)
def test_form_field_labels(monkeypatch, table, expected):
    monkeypatch.setattr(translations, "generate_translations", lambda language: table)
    assert translations.form_field_labels("en-GB") == expected


LABELS = {"note": "Notes", "note_info": "Notes and reminders", "vlan_info": "The vlan id", "email": "E-mail"}


@pytest.mark.parametrize(
    "prop,expected",
    [
        pytest.param(
            ("note", {"type": "string", "title": "Note"}),
            {"type": "string", "title": "Notes", "description": "Notes and reminders"},
            id="label-and-help-text",
        ),
        pytest.param(
            ("vlan", {"type": "integer", "description": "as the form says"}),
            {"type": "integer", "description": "as the form says"},
            id="a-description-the-schema-has-is-kept",
        ),
        pytest.param(
            ("speed", {"type": "string", "title": "Speed"}),
            {"type": "string", "title": "Speed"},
            id="no-label-untouched",
        ),
        pytest.param(
            ("contact", {"type": "object", "properties": {"email": {"type": "string", "title": "Email"}}}),
            {"type": "object", "properties": {"email": {"type": "string", "title": "E-mail"}}},
            id="a-nested-objects-fields",
        ),
        pytest.param(
            ("ports", {"type": "array", "items": {"type": "object", "properties": {"vlan": {"type": "integer"}}}}),
            {
                "type": "array",
                "items": {"type": "object", "properties": {"vlan": {"type": "integer", "description": "The vlan id"}}},
            },
            id="a-lists-items",
        ),
    ],
)
def test_label_schema(prop, expected):
    name, schema_prop = prop
    schema = {"type": "object", "properties": {name: schema_prop}, "required": [name]}
    labelled = translations.label_schema(schema, LABELS)
    assert labelled["properties"][name] == expected
    assert labelled["required"] == [name] and schema["properties"][name] == schema_prop  # the input is not mutated
