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


from pydantic_settings import BaseSettings

from orchestrator.core.utils.expose_settings import SettingsEnvVariablesSchema, SettingsExposedSchema

EXPOSED_ENV_SETTINGS_REGISTRY: dict[str, BaseSettings] = {}
EXPOSED_ENV_SETTINGS_INCLUDES: dict[str, set[str]] = {}


def expose_settings(settings_name: str, base_settings: BaseSettings, include: set[str] | None = None) -> BaseSettings:
    """Decorator to register settings classes.

    Pass `include` to expose only the given fields instead of all fields.
    """
    EXPOSED_ENV_SETTINGS_REGISTRY[settings_name] = base_settings
    if include is None:
        EXPOSED_ENV_SETTINGS_INCLUDES.pop(settings_name, None)
    else:
        EXPOSED_ENV_SETTINGS_INCLUDES[settings_name] = include
    return base_settings


def get_all_exposed_settings() -> list[SettingsExposedSchema]:
    """Return all registered settings as dicts."""

    def _get_settings_env_variables(
        base_settings: BaseSettings, include: set[str] | None
    ) -> list[SettingsEnvVariablesSchema]:
        """Get environment variables from settings."""
        settings_env_variables: list[SettingsEnvVariablesSchema] = [
            SettingsEnvVariablesSchema(env_name=key, env_value=value)
            for key, value in base_settings.model_dump(include=include).items()
        ]
        return sorted(settings_env_variables, key=lambda v: v.env_name)

    return [
        SettingsExposedSchema(
            name=name, variables=_get_settings_env_variables(base_settings, EXPOSED_ENV_SETTINGS_INCLUDES.get(name))
        )
        for name, base_settings in EXPOSED_ENV_SETTINGS_REGISTRY.items()
    ]
