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
from typing import Dict

from orchestrator.settings import app_settings


def generate_translations(language: str) -> Dict[str, str]:
    translations_dir = app_settings.TRANSLATIONS_DIR or Path(__file__).parent.parent / "workflows" / "translations"
    filename = translations_dir / f"{language}.json"

    if not filename.exists():
        return {}

    with filename.open() as translation_file:
        data = json.load(translation_file)
        if not isinstance(data, dict):
            return {}
        return data
