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
"""Utility module for exposing settings in a structured format.

Unfortunately, this module needs to be imported from the utils and cannot be added to the schemas folder.
This is due to circular import issues with the combination of schemas/settings.
"""

from typing import Any

from pydantic import BaseModel
from pydantic_core import core_schema


class SecretStr(str):
    """A string that is treated as a secret, for example, passwords or API keys.

    This class is used to indicate that the string should not be logged or displayed in plaintext.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):  # type: ignore
        # This method is used to define how the SecretStr type should be handled by Pydantic.
        # With this implementation, it will fail validation.
        return core_schema.no_info_plain_validator_function(cls)


class SettingsEnvVariablesSchema(BaseModel):
    env_name: str
    env_value: Any


class SettingsExposedSchema(BaseModel):
    name: str
    variables: list[SettingsEnvVariablesSchema]
