from pydantic import PostgresDsn
from pydantic import SecretStr as PydanticSecretStr
from pydantic_settings import BaseSettings

from orchestrator.services.settings_env_variables import MASK, expose_settings, get_all_exposed_settings
from orchestrator.utils.expose_settings import SecretStr as OrchSecretStr


def test_expose_settings():

    class MySettings(BaseSettings):
        api_key: OrchSecretStr = "test_api_key"
        db_password: PydanticSecretStr = "test_password"  # noqa: S105
        debug_mode: bool = True
        secret_test: str = "test_secret"  # noqa: S105
        uri: PostgresDsn = "postgresql://user:password@localhost/dbname"

    my_settings = MySettings()
    expose_settings("my_settings", my_settings)

    exposed_settings = get_all_exposed_settings()

    assert len(exposed_settings) == 1
    my_settings_index = 0

    assert exposed_settings[my_settings_index].name == "my_settings"

    assert len(exposed_settings[my_settings_index].variables) == 5

    # Assert that sensitive values are masked
    assert exposed_settings[my_settings_index].variables[0].env_value == MASK  # api_key
    assert exposed_settings[my_settings_index].variables[1].env_value == MASK  # db_password
    assert exposed_settings[my_settings_index].variables[2].env_value is True  # debug_mode
    assert exposed_settings[my_settings_index].variables[3].env_value == MASK  # secret_test
    assert exposed_settings[my_settings_index].variables[4].env_value == MASK  # uri
