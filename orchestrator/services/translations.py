# Copyright 2019-2020 SURF.
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
from pathlib import Path
from typing import Union

from orchestrator.settings import app_settings

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
