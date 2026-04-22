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

from pydantic import SecretStr
from pydantic_settings import BaseSettings

from orchestrator.services.settings_env_variables import expose_settings, get_all_exposed_settings
from orchestrator.settings import SecretPostgresDsn, SecretRedisDsn


def test_expose_settings():

    class MySettings(BaseSettings):
        api_key: SecretStr = "test_api_key"
        db_password: SecretStr = "test_password"  # noqa: S105
        debug_mode: bool = True
        secret_test: SecretStr = "test_secret"  # noqa: S105
        uri: SecretPostgresDsn = "postgresql+psycopg://user:password@localhost/dbname"
        cache_uri: SecretRedisDsn = "rediss://user:password@localhost/dbname"

    my_settings = MySettings()
    expose_settings("my_settings", my_settings)

    exposed_settings = get_all_exposed_settings()

    assert len(exposed_settings) == 1
    my_settings_index = 0

    assert exposed_settings[my_settings_index].name == "my_settings"

    assert len(exposed_settings[my_settings_index].variables) == 6

    # Assert that sensitive values are masked (Note that the order is different because get_all_exposed_settings() sorts the setting names)
    assert exposed_settings[my_settings_index].variables[0].env_value.__repr__() == "SecretStr('**********')"  # api_key
    assert exposed_settings[my_settings_index].variables[1].env_value.__repr__() == "Secret('**********')"  # cache_uri
    assert (
        exposed_settings[my_settings_index].variables[2].env_value.__repr__() == "SecretStr('**********')"
    )  # db_password
    assert exposed_settings[my_settings_index].variables[3].env_value is True  # debug_mode
    assert (
        exposed_settings[my_settings_index].variables[4].env_value.__repr__() == "SecretStr('**********')"
    )  # secret_test
    assert exposed_settings[my_settings_index].variables[5].env_value.__repr__() == "Secret('**********')"  # uri
