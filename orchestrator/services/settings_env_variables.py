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

from pydantic import SecretStr as PydanticSecretStr
from pydantic_core import MultiHostUrl, Url
from pydantic_settings import BaseSettings

from orchestrator.utils.expose_settings import SecretStr as OrchSecretStr
from orchestrator.utils.expose_settings import SettingsEnvVariablesSchema, SettingsExposedSchema

EXPOSED_ENV_SETTINGS_REGISTRY: Dict[str, Type[BaseSettings]] = {}
MASK = "**********"


def expose_settings(settings_name: str, base_settings: Type[BaseSettings]) -> Type[BaseSettings]:
    """Decorator to register settings classes."""
    EXPOSED_ENV_SETTINGS_REGISTRY[settings_name] = base_settings
    return base_settings


def mask_value(key: str, value: Any) -> Any:
    key_lower = key.lower()
    is_sensitive_key = "secret" in key_lower or "password" in key_lower

    if is_sensitive_key or isinstance(value, (OrchSecretStr, PydanticSecretStr, MultiHostUrl, Url)):
        return MASK

    return value


def get_all_exposed_settings() -> list[SettingsExposedSchema]:
    """Return all registered settings as dicts."""

    def _get_settings_env_variables(base_settings: Type[BaseSettings]) -> list[SettingsEnvVariablesSchema]:
        """Get environment variables from settings."""
        return [
            SettingsEnvVariablesSchema(env_name=key, env_value=mask_value(key, value))
            for key, value in base_settings.model_dump().items()  # type: ignore
        ]

    return [
        SettingsExposedSchema(name=name, variables=_get_settings_env_variables(base_settings))
        for name, base_settings in EXPOSED_ENV_SETTINGS_REGISTRY.items()
    ]
