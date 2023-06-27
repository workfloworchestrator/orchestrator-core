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

import structlog
from fastapi.routing import APIRouter
from pydantic import constr

from orchestrator.services.translations import generate_translations

logger = structlog.get_logger(__name__)


router = APIRouter()

language_str = constr(regex="^[a-z]+-[A-Z]+$")


@router.get("/{language}", response_model=dict)
def get_translations(language: language_str) -> dict:  # type: ignore
    translations = generate_translations(language)

    return translations
