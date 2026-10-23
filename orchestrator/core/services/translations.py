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
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Union

from orchestrator.core.settings import app_settings

Translations = dict[str, Union[dict, str]]


def _load_translations_file(language: str, translations_dir: Path) -> Translations:
    filename = translations_dir / f"{language}.json"
    if not filename.exists():
        return {}

    with filename.open() as translation_file:
        data = json.load(translation_file)
        if not isinstance(data, dict):
            return {}
        return data


def _deep_merge_dict(d1: dict, d2: dict) -> Translations:
    for k, v in d2.items():
        if isinstance(d1.get(k), dict) and isinstance(v, dict):
            d1[k] = _deep_merge_dict(d1[k], v)
        else:
            d1[k] = v
    return d1


def generate_translations(language: str) -> Translations:
    translations = _load_translations_file(language, Path(__file__).parent.parent / "workflows" / "translations")
    user_translations = (
        _load_translations_file(language, app_settings.TRANSLATIONS_DIR) if app_settings.TRANSLATIONS_DIR else {}
    )
    return _deep_merge_dict(translations, user_translations)


def form_field_labels(language: str) -> dict[str, str]:
    """The form field labels of ``language``: a field's label under its name, its help text under ``<name>_info``.

    These are the ``forms.fields`` translations the frontend shows for a form; a language without them gives {}.
    """
    forms = generate_translations(language).get("forms")
    fields = forms.get("fields") if isinstance(forms, dict) else None
    return {name: text for name, text in fields.items() if isinstance(text, str)} if isinstance(fields, dict) else {}


def label_schema(schema: Mapping[str, Any], labels: Mapping[str, str]) -> dict[str, Any]:
    """``schema`` with each property titled by its field label and described by its help text, where ``labels`` has them.

    A nested object's properties and a list's items are labelled the same way. A property keeps a ``description``
    it already has, and a field without a label keeps the schema's own title.
    """
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return dict(schema)
    return {**schema, "properties": {name: _label_property(name, prop, labels) for name, prop in properties.items()}}


def _label_property(name: str, prop: Any, labels: Mapping[str, str]) -> Any:
    if not isinstance(prop, dict):
        return prop
    labelled = label_schema(prop, labels)
    if isinstance(labelled.get("items"), dict):
        labelled["items"] = label_schema(labelled["items"], labels)
    if label := labels.get(name):
        labelled["title"] = label
    if (info := labels.get(f"{name}_info")) and "description" not in labelled:
        labelled["description"] = info
    return labelled
