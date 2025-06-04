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

from typing import Any, Dict, Type

from pydantic import BaseModel, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings


class SettingsEnvVariablesSchema(BaseModel):
    env_name: str
    env_value: Any


class SettingsExposedSchema(BaseModel):
    name: str
    settings_variables: list[SettingsEnvVariablesSchema]


EXPOSED_ENV_SETTINGS_REGISTRY: Dict[str, Type[BaseSettings]] = {}


def expose_settings(settings_name: str, base_settings: Type[BaseSettings]) -> Type[BaseSettings]:
    """Decorator to register settings classes."""
    EXPOSED_ENV_SETTINGS_REGISTRY[settings_name] = base_settings
    return base_settings


def sanitize_value(key: str, value: Any) -> Any:
    key_lower = key.lower()

    if "secret" in key_lower or "password" in key_lower:
        # Mask sensitive information
        return "**********"
    if isinstance(value, SecretStr):
        # Need to convert SecretStr to str for serialization
        return str(value)
    if isinstance(value, PostgresDsn):
        # Convert PostgresDsn to str for serialization
        return "**********"

    return value


def get_all_exposed_settings() -> list[SettingsExposedSchema]:
    """Return all registered settings as dicts."""
    return [
        SettingsExposedSchema(
            name=name,
            settings_variables=[
                SettingsEnvVariablesSchema(env_name=key, env_value=sanitize_value(key, value))
                for key, value in base_settings.model_dump().items()  # type: ignore
            ],
        )
        for name, base_settings in EXPOSED_ENV_SETTINGS_REGISTRY.items()
    ]
