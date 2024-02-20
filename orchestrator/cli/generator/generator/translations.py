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
from collections.abc import Callable

import structlog

from orchestrator.cli.generator.generator.settings import product_generator_settings as settings

logger = structlog.getLogger(__name__)


def read_translations() -> dict:
    path = settings.FOLDER_PREFIX / settings.TRANSLATION_PATH
    try:
        with open(path) as stream:
            try:
                return json.load(stream)
            except ValueError:
                logger.error("Failed to parse translation file.")
    except FileNotFoundError:
        logger.info("creating missing translations file", path=str(path))
        return {"workflow": {}}

    return {}


def add_workflow_translations(config: dict, writer: Callable) -> None:
    if translations := read_translations():
        variable = config["variable"]
        name = config["name"]
        workflows = {
            f"create_{variable}": f"Create {name}",
            f"modify_{variable}": f"Modify {name}",
            f"validate_{variable}": f"Validate {name}",
            f"terminate_{variable}": f"Terminate {name}",
        }
        translations["workflow"] = translations["workflow"] | workflows

        path = settings.FOLDER_PREFIX / settings.TRANSLATION_PATH
        writer(path, json.dumps(translations, sort_keys=True, indent=4) + "\n")
