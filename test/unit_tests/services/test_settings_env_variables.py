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

"""Tests for settings exposure: registry operations, field extraction, and multi-registration behavior."""

import pytest
from pydantic_settings import BaseSettings

from orchestrator.core.services.settings_env_variables import (
    EXPOSED_ENV_SETTINGS_REGISTRY,
    expose_settings,
    get_all_exposed_settings,
)
from orchestrator.core.utils.expose_settings import SettingsEnvVariablesSchema, SettingsExposedSchema


@pytest.fixture(autouse=True)
def clear_registry():
    """Isolate each test by clearing the global registry before and after."""
    EXPOSED_ENV_SETTINGS_REGISTRY.clear()
    yield
    EXPOSED_ENV_SETTINGS_REGISTRY.clear()


class _SimpleSettings(BaseSettings):
    host: str = "localhost"
    port: int = 5432
    debug: bool = False


class _AnotherSettings(BaseSettings):
    api_url: str = "https://example.com"
    timeout: int = 30


def test_expose_settings_registers_in_dict():
    settings = _SimpleSettings()
    result = expose_settings("simple", settings)

    assert "simple" in EXPOSED_ENV_SETTINGS_REGISTRY
    assert EXPOSED_ENV_SETTINGS_REGISTRY["simple"] is settings
    assert result is settings


def test_expose_settings_returns_same_object():
    settings = _SimpleSettings()
    returned = expose_settings("simple", settings)
    assert returned is settings


def test_expose_settings_overwrites_existing_key():
    settings_a = _SimpleSettings()
    settings_b = _SimpleSettings(host="otherhost")
    expose_settings("simple", settings_a)
    expose_settings("simple", settings_b)

    assert EXPOSED_ENV_SETTINGS_REGISTRY["simple"] is settings_b


def test_get_all_exposed_settings_returns_empty_when_no_registrations():
    result = get_all_exposed_settings()
    assert result == []


def test_get_all_exposed_settings_returns_one_entry():
    settings = _SimpleSettings()
    expose_settings("simple", settings)

    result = get_all_exposed_settings()

    assert len(result) == 1
    assert isinstance(result[0], SettingsExposedSchema)
    assert result[0].name == "simple"


def test_get_all_exposed_settings_variables_are_sorted_by_name():
    settings = _SimpleSettings()
    expose_settings("simple", settings)

    result = get_all_exposed_settings()
    variable_names = [v.env_name for v in result[0].variables]

    assert variable_names == sorted(variable_names)


def test_get_all_exposed_settings_contains_all_fields():
    settings = _SimpleSettings()
    expose_settings("simple", settings)

    result = get_all_exposed_settings()
    variable_names = {v.env_name for v in result[0].variables}

    assert variable_names == {"host", "port", "debug"}


def test_get_all_exposed_settings_variable_values_are_correct():
    settings = _SimpleSettings()
    expose_settings("simple", settings)

    result = get_all_exposed_settings()
    variables_by_name = {v.env_name: v.env_value for v in result[0].variables}

    assert variables_by_name["host"] == "localhost"
    assert variables_by_name["port"] == 5432
    assert variables_by_name["debug"] is False


def test_get_all_exposed_settings_variables_schema_type():
    settings = _SimpleSettings()
    expose_settings("simple", settings)

    result = get_all_exposed_settings()
    for variable in result[0].variables:
        assert isinstance(variable, SettingsEnvVariablesSchema)


def test_get_all_exposed_settings_multiple_registrations():
    expose_settings("simple", _SimpleSettings())
    expose_settings("another", _AnotherSettings())

    result = get_all_exposed_settings()

    assert len(result) == 2
    names = {entry.name for entry in result}
    assert names == {"simple", "another"}


def test_get_all_exposed_settings_multiple_registrations_correct_variable_counts():
    expose_settings("simple", _SimpleSettings())
    expose_settings("another", _AnotherSettings())

    result = get_all_exposed_settings()
    counts_by_name = {entry.name: len(entry.variables) for entry in result}

    assert counts_by_name["simple"] == 3
    assert counts_by_name["another"] == 2
