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


from typing import NamedTuple

from pydantic_settings import BaseSettings

from orchestrator.core.utils.expose_settings import SettingsEnvVariablesSchema, SettingsExposedSchema


class ExposedSettings(NamedTuple):
    """A registered settings instance and the fields to expose (`None` exposes all fields)."""

    settings: BaseSettings
    include: set[str] | None = None


EXPOSED_ENV_SETTINGS_REGISTRY: dict[str, ExposedSettings] = {}


def expose_settings(settings_name: str, base_settings: BaseSettings, include: set[str] | None = None) -> BaseSettings:
    """Decorator to register settings classes.

    Pass `include` to expose only the given fields instead of all fields.
    """
    EXPOSED_ENV_SETTINGS_REGISTRY[settings_name] = ExposedSettings(base_settings, include)
    return base_settings


def get_all_exposed_settings() -> list[SettingsExposedSchema]:
    """Return all registered settings as dicts."""

    def _get_settings_env_variables(exposed: ExposedSettings) -> list[SettingsEnvVariablesSchema]:
        """Get environment variables from settings."""
        settings_env_variables: list[SettingsEnvVariablesSchema] = [
            SettingsEnvVariablesSchema(env_name=key, env_value=value)
            for key, value in exposed.settings.model_dump(include=exposed.include).items()
        ]
        return sorted(settings_env_variables, key=lambda v: v.env_name)

    return [
        SettingsExposedSchema(name=name, variables=_get_settings_env_variables(exposed))
        for name, exposed in EXPOSED_ENV_SETTINGS_REGISTRY.items()
    ]
