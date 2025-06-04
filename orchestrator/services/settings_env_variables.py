# Copyright 2019-2025 SURF.
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

from typing import Type, Dict, Any
from pydantic import BaseModel
from orchestrator.schemas import SettingsEnvVariablesSchema

from oauth2_lib.settings import oauth2lib_settings


EXPOSED_ENV_SETTINGS_REGISTRY: Dict[str, Type[BaseModel]] = {
    "oauth2lib_settings": oauth2lib_settings,  # Manually register the oauth_settings

}

def expose_settings(cls: Type[BaseModel]) -> Type[BaseModel]:
    """Decorator to register settings classes."""
    EXPOSED_ENV_SETTINGS_REGISTRY[cls.__name__] = cls
    return cls


def get_all_exposed_settings() -> list[SettingsEnvVariablesSchema]:
    """Return all registered settings as dicts."""
    return [
        SettingsEnvVariablesSchema(env_name=name, env_value=cls.model_dump())
        for name, cls in EXPOSED_ENV_SETTINGS_REGISTRY.items()
    ]
